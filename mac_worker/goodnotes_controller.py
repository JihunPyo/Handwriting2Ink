from __future__ import annotations

import argparse
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from goodnotes_writer import load_strokes
from goodnotes_writer import filter_strokes_by_distance
from goodnotes_writer import install_abort_handlers
from goodnotes_writer import map_strokes
from goodnotes_writer import raise_if_aborted
from goodnotes_writer import replay_with_pyautogui
from goodnotes_writer import sample_strokes
from goodnotes_writer import stroke_bbox
from goodnotes_writer import summarize

GOODNOTES_APP_NAMES = ("Goodnotes", "GoodNotes")
QUARTZ_REPLAY_SOURCE = PROJECT_ROOT / "mac_worker" / "goodnotes_quartz_replay.swift"
QUARTZ_REPLAY_BINARY = Path("/private/tmp/h2i_goodnotes_quartz_replay")

Point = tuple[float, float]
Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class ControllerConfig:
    pen_button_point: Point | None = None
    black_color_point: Point | None = None
    paper_rect: Rect | None = None
    driver: str = "down_move"
    tool_select_mode: str = "hotkey"
    pen_hotkey: str = "cmd+p"
    lasso_hotkey: str = "cmd+l"
    target_rect: Rect | None = None
    fit: str = "contain"
    sample_step: int = 1
    min_point_distance: float = 1.0
    input_backend: str = "quartz"
    point_delay: float = 0.002
    stroke_delay: float = 0.04
    quartz_point_delay: float = 0.0015
    quartz_stroke_delay: float = 0.008
    quartz_mouse_down_delay: float = 0.006
    quartz_post_draw_delay: float = 0.8
    lasso_driver: str = "drag"
    lasso_shape: str = "rectangle"
    lasso_point_count: int = 120
    lasso_close_overlap: float = 32.0
    lasso_padding: float = 24.0
    lasso_drag_duration: float = 0.8
    lasso_tool_delay: float = 0.6
    copy_hotkey: str = "command+c"
    copy_delay: float = 0.8
    copy_retries: int = 2
    copy_retry_delay: float = 0.3
    countdown: float = 2.0
    line_length: float = 15.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "GoodNotes를 전면/전체화면으로 올리고, 펜을 선택한 뒤, "
            "중앙에 짧은 절대좌표 테스트 선을 입력합니다."
        )
    )
    parser.add_argument("--config", default="mac_worker/config.json", help="워커 설정 JSON 경로")
    parser.add_argument("--pen_point", default=None, help="펜 버튼 절대 좌표 x,y")
    parser.add_argument("--black_color_point", default=None, help="검은색 색상 버튼 절대 좌표 x,y")
    parser.add_argument("--paper_rect", default=None, help="종이 영역 절대 좌표 x,y,width,height")
    parser.add_argument("--strokes", default=None, help="GoodNotes에 그릴 strokes.json 경로")
    parser.add_argument("--target_rect", default=None, help="stroke를 매핑할 GoodNotes 종이 영역 x,y,width,height")
    parser.add_argument(
        "--fit",
        choices=("contain", "stretch"),
        default=None,
        help="stroke bbox를 target_rect에 맞추는 방식",
    )
    parser.add_argument("--sample_step", type=int, default=None, help="N개 점마다 하나씩 사용")
    parser.add_argument("--min_point_distance", type=float, default=None, help="매핑 후 이 거리(px) 미만으로 움직인 점 생략")
    parser.add_argument(
        "--input_backend",
        choices=("quartz", "pyautogui"),
        default=None,
        help="stroke/올가미 마우스 입력 backend. 기본값은 quartz",
    )
    parser.add_argument("--point_delay", type=float, default=None, help="stroke point 사이 입력 지연")
    parser.add_argument("--stroke_delay", type=float, default=None, help="stroke 사이 입력 지연")
    parser.add_argument("--quartz_point_delay", type=float, default=None, help="Quartz stroke point 사이 입력 지연")
    parser.add_argument("--quartz_stroke_delay", type=float, default=None, help="Quartz stroke 사이 입력 지연")
    parser.add_argument("--quartz_mouse_down_delay", type=float, default=None, help="Quartz mouseDown 직후 drag 전 대기 시간")
    parser.add_argument("--quartz_post_draw_delay", type=float, default=None, help="Quartz stroke 입력 후 올가미 전환 전 대기 시간")
    parser.add_argument(
        "--copy_after_draw",
        action="store_true",
        help="stroke 입력 후 cmd+l로 올가미를 선택하고 stroke bbox 주변을 드래그한 뒤 cmd+c를 실행합니다.",
    )
    parser.add_argument("--lasso_padding", type=float, default=None, help="자동 올가미 bbox padding(px)")
    parser.add_argument("--lasso_drag_duration", type=float, default=None, help="올가미 사각형 드래그 시간")
    parser.add_argument(
        "--lasso_shape",
        choices=("rectangle", "ellipse"),
        default=None,
        help="올가미 경로 모양. 기본값 rectangle",
    )
    parser.add_argument("--lasso_point_count", type=int, default=None, help="올가미 경로 중간점 개수")
    parser.add_argument("--lasso_close_overlap", type=float, default=None, help="올가미 닫기 시 시작 변을 겹쳐 지나가는 거리")
    parser.add_argument(
        "--lasso_driver",
        choices=("drag", "down_move"),
        default=None,
        help="올가미 드래그 입력 방식. macOS/GoodNotes에서는 drag 권장",
    )
    parser.add_argument("--lasso_tool_delay", type=float, default=None, help="cmd+l 후 올가미 입력 전 대기 시간")
    parser.add_argument("--copy_hotkey", default=None, help="복사 단축키. 기본값 command+c")
    parser.add_argument("--copy_delay", type=float, default=None, help="올가미 mouseUp 후 복사 전 대기 시간")
    parser.add_argument("--copy_retries", type=int, default=None, help="복사 단축키 반복 횟수")
    parser.add_argument("--copy_retry_delay", type=float, default=None, help="복사 단축키 반복 간 대기 시간")
    parser.add_argument("--line_center", default=None, help="테스트 선 중심 절대 좌표 x,y")
    parser.add_argument("--line_length", type=float, default=None, help="테스트 선 길이(px). 기본값 15")
    parser.add_argument("--countdown", type=float, default=None, help="실제 선 입력 전 대기 시간")
    parser.add_argument("--driver", choices=("drag", "down_move"), default=None, help="마우스 입력 방식")
    parser.add_argument(
        "--tool_select_mode",
        choices=("hotkey", "point"),
        default=None,
        help="펜 도구 선택 방식. 기본값은 GoodNotes 단축키 hotkey",
    )
    parser.add_argument("--pen_hotkey", default=None, help="펜 선택 단축키. 기본값 cmd+p")
    parser.add_argument("--lasso_hotkey", default=None, help="올가미 선택 단축키. 기본값 cmd+l")
    parser.add_argument(
        "--select_lasso_after_draw",
        action="store_true",
        help="테스트 선 입력 후 올가미 도구까지 선택합니다.",
    )
    parser.add_argument(
        "--skip_fullscreen",
        action="store_true",
        help="GoodNotes 전체화면 전환을 생략합니다.",
    )
    parser.add_argument(
        "--require_pen_point",
        action="store_true",
        help="호환용 옵션입니다. 실제 실행에서는 기본적으로 펜 버튼 좌표가 필요합니다.",
    )
    parser.add_argument(
        "--skip_pen_select",
        action="store_true",
        help="펜 선택을 생략하고 현재 선택된 도구로 테스트 선만 입력합니다.",
    )
    parser.add_argument("--execute", action="store_true", help="실제 GUI 조작과 마우스 입력을 수행합니다.")
    return parser.parse_args()


def resolve_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def parse_point(value: str | None) -> Point | None:
    if not value:
        return None
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 2:
        raise ValueError("좌표는 x,y 형식이어야 합니다.")
    return parts[0], parts[1]


def parse_rect(value: str | None) -> Rect | None:
    if not value:
        return None
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("영역은 x,y,width,height 형식이어야 합니다.")
    x, y, width, height = parts
    if width <= 0 or height <= 0:
        raise ValueError("영역 width/height는 0보다 커야 합니다.")
    return x, y, width, height


def load_json_config(path: str) -> dict[str, Any]:
    config_path = resolve_path(path)
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def controller_config(raw: dict[str, Any], args: argparse.Namespace) -> ControllerConfig:
    section = raw.get("goodnotes_controller", {})
    if not isinstance(section, dict):
        section = {}

    pen_point = parse_point(args.pen_point) or parse_point(section.get("pen_button_point"))
    black_color_point = parse_point(args.black_color_point) or parse_point(section.get("black_color_point"))
    paper_rect = parse_rect(args.paper_rect) or parse_rect(section.get("paper_rect"))
    target_rect = (
        parse_rect(args.target_rect)
        or parse_rect(section.get("target_rect"))
        or parse_rect(raw.get("target_rect"))
    )
    driver = args.driver or section.get("driver") or "down_move"
    tool_select_mode = args.tool_select_mode or section.get("tool_select_mode") or "hotkey"
    pen_hotkey = args.pen_hotkey or section.get("pen_hotkey") or "cmd+p"
    lasso_hotkey = args.lasso_hotkey or section.get("lasso_hotkey") or "cmd+l"
    fit = args.fit or section.get("fit") or raw.get("fit") or "contain"
    sample_step = (
        args.sample_step if args.sample_step is not None else int(section.get("sample_step", raw.get("sample_step", 1)))
    )
    min_point_distance = (
        args.min_point_distance
        if args.min_point_distance is not None
        else float(section.get("min_point_distance", raw.get("min_point_distance", 1.0)))
    )
    input_backend = args.input_backend or section.get("input_backend") or raw.get("input_backend") or "quartz"
    if input_backend not in {"quartz", "pyautogui"}:
        raise ValueError("input_backend는 quartz 또는 pyautogui여야 합니다.")
    point_delay = (
        args.point_delay
        if args.point_delay is not None
        else float(section.get("point_delay", raw.get("point_delay", 0.002)))
    )
    stroke_delay = (
        args.stroke_delay
        if args.stroke_delay is not None
        else float(section.get("stroke_delay", raw.get("stroke_delay", 0.04)))
    )
    quartz_point_delay = (
        args.quartz_point_delay
        if args.quartz_point_delay is not None
        else float(section.get("quartz_point_delay", raw.get("quartz_point_delay", 0.0015)))
    )
    quartz_stroke_delay = (
        args.quartz_stroke_delay
        if args.quartz_stroke_delay is not None
        else float(section.get("quartz_stroke_delay", raw.get("quartz_stroke_delay", 0.008)))
    )
    quartz_mouse_down_delay = (
        args.quartz_mouse_down_delay
        if args.quartz_mouse_down_delay is not None
        else float(section.get("quartz_mouse_down_delay", raw.get("quartz_mouse_down_delay", 0.006)))
    )
    quartz_post_draw_delay = (
        args.quartz_post_draw_delay
        if args.quartz_post_draw_delay is not None
        else float(section.get("quartz_post_draw_delay", raw.get("quartz_post_draw_delay", 0.8)))
    )
    lasso_driver = args.lasso_driver or section.get("lasso_driver") or "drag"
    lasso_shape = args.lasso_shape or section.get("lasso_shape") or "rectangle"
    lasso_point_count = (
        args.lasso_point_count
        if args.lasso_point_count is not None
        else int(section.get("lasso_point_count", 120))
    )
    lasso_close_overlap = (
        args.lasso_close_overlap
        if args.lasso_close_overlap is not None
        else float(section.get("lasso_close_overlap", 32.0))
    )
    lasso_padding = (
        args.lasso_padding
        if args.lasso_padding is not None
        else float(section.get("lasso_padding", 24.0))
    )
    lasso_drag_duration = (
        args.lasso_drag_duration
        if args.lasso_drag_duration is not None
        else float(section.get("lasso_drag_duration", 0.8))
    )
    lasso_tool_delay = (
        args.lasso_tool_delay
        if args.lasso_tool_delay is not None
        else float(section.get("lasso_tool_delay", 0.6))
    )
    copy_hotkey = args.copy_hotkey or section.get("copy_hotkey") or "command+c"
    copy_delay = (
        args.copy_delay
        if args.copy_delay is not None
        else float(section.get("copy_delay", 0.8))
    )
    copy_retries = (
        args.copy_retries
        if args.copy_retries is not None
        else int(section.get("copy_retries", 2))
    )
    copy_retry_delay = (
        args.copy_retry_delay
        if args.copy_retry_delay is not None
        else float(section.get("copy_retry_delay", 0.3))
    )
    countdown = args.countdown if args.countdown is not None else float(section.get("countdown", 2.0))
    line_length = (
        args.line_length if args.line_length is not None else float(section.get("line_length", 15.0))
    )
    return ControllerConfig(
        pen_button_point=pen_point,
        black_color_point=black_color_point,
        paper_rect=paper_rect,
        driver=driver,
        tool_select_mode=tool_select_mode,
        pen_hotkey=pen_hotkey,
        lasso_hotkey=lasso_hotkey,
        target_rect=target_rect,
        fit=fit,
        sample_step=sample_step,
        min_point_distance=min_point_distance,
        input_backend=input_backend,
        point_delay=point_delay,
        stroke_delay=stroke_delay,
        quartz_point_delay=quartz_point_delay,
        quartz_stroke_delay=quartz_stroke_delay,
        quartz_mouse_down_delay=quartz_mouse_down_delay,
        quartz_post_draw_delay=quartz_post_draw_delay,
        lasso_driver=lasso_driver,
        lasso_shape=lasso_shape,
        lasso_point_count=lasso_point_count,
        lasso_close_overlap=lasso_close_overlap,
        lasso_padding=lasso_padding,
        lasso_drag_duration=lasso_drag_duration,
        lasso_tool_delay=lasso_tool_delay,
        copy_hotkey=copy_hotkey,
        copy_delay=copy_delay,
        copy_retries=copy_retries,
        copy_retry_delay=copy_retry_delay,
        countdown=countdown,
        line_length=line_length,
    )


def prepare_mapped_strokes(strokes_path: Path, config: ControllerConfig) -> list[list[Point]]:
    if config.target_rect is None:
        raise RuntimeError("--strokes 사용 시 --target_rect 또는 config target_rect가 필요합니다.")
    strokes = load_strokes(strokes_path)
    strokes = sample_strokes(strokes, config.sample_step)
    source = stroke_bbox(strokes)
    mapped = map_strokes(strokes, source, config.target_rect, config.fit)
    mapped = filter_strokes_by_distance(mapped, config.min_point_distance)
    summarize(mapped, source, config.target_rect)
    return mapped


def padded_rect(rect: Rect, padding: float) -> Rect:
    x, y, width, height = rect
    padding = max(0.0, padding)
    return x - padding, y - padding, width + padding * 2.0, height + padding * 2.0


def run_osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or "osascript 실행에 실패했습니다.")
    return result.stdout.strip()


def activate_goodnotes() -> str:
    errors = []
    for app_name in GOODNOTES_APP_NAMES:
        result = subprocess.run(
            ["osascript", "-e", f'tell application "{app_name}" to activate'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            time.sleep(0.5)
            return app_name
        errors.append((result.stderr or result.stdout).strip())
    raise RuntimeError(f"GoodNotes 활성화에 실패했습니다: {' | '.join(errors)}")


def require_frontmost_goodnotes() -> str:
    frontmost = run_osascript(
        'tell application "System Events" to get name of first application process whose frontmost is true'
    )
    if frontmost not in GOODNOTES_APP_NAMES:
        raise RuntimeError(f"GoodNotes가 전면 앱이 아닙니다: {frontmost}")
    return frontmost


def set_goodnotes_fullscreen(process_name: str) -> None:
    script = f'''
tell application "System Events"
  tell application process "{process_name}"
    set frontmost to true
    delay 0.2
    try
      set value of attribute "AXFullScreen" of window 1 to true
    on error
      keystroke "f" using {{control down, command down}}
    end try
  end tell
end tell
'''
    run_osascript(script)
    time.sleep(1.0)


def ensure_quartz_replay_binary() -> Path:
    if not QUARTZ_REPLAY_SOURCE.exists():
        raise RuntimeError(f"Quartz replay Swift source를 찾지 못했습니다: {QUARTZ_REPLAY_SOURCE}")

    should_build = not QUARTZ_REPLAY_BINARY.exists()
    if not should_build:
        should_build = QUARTZ_REPLAY_SOURCE.stat().st_mtime > QUARTZ_REPLAY_BINARY.stat().st_mtime
    if not should_build:
        return QUARTZ_REPLAY_BINARY

    env = os.environ.copy()
    env.setdefault("CLANG_MODULE_CACHE_PATH", "/private/tmp/h2i_clang_module_cache")
    subprocess.run(
        [
            "swiftc",
            "-O",
            str(QUARTZ_REPLAY_SOURCE),
            "-o",
            str(QUARTZ_REPLAY_BINARY),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )
    return QUARTZ_REPLAY_BINARY


def run_quartz_payload(payload: dict[str, Any]) -> None:
    binary_path = ensure_quartz_replay_binary()
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        suffix=".json",
        prefix="h2i_quartz_",
        dir="/private/tmp",
        delete=False,
    ) as file:
        json.dump(payload, file, ensure_ascii=False)
        payload_path = Path(file.name)

    command = [str(binary_path), "--payload", str(payload_path)]
    process: subprocess.Popen[Any] | None = None
    try:
        process = subprocess.Popen(command, cwd=PROJECT_ROOT)
        while True:
            return_code = process.poll()
            if return_code is not None:
                if return_code != 0:
                    raise subprocess.CalledProcessError(return_code, command)
                return
            raise_if_aborted()
            time.sleep(0.05)
    except KeyboardInterrupt:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise
    finally:
        payload_path.unlink(missing_ok=True)


def replay_strokes_with_backend(strokes: list[list[Point]], config: ControllerConfig) -> None:
    if config.input_backend == "quartz":
        run_quartz_payload(
            {
                "kind": "strokes",
                "strokes": strokes,
                "point_delay": max(config.quartz_point_delay, 0.0),
                "stroke_delay": max(config.quartz_stroke_delay, 0.0),
                "mouse_down_delay": max(config.quartz_mouse_down_delay, 0.0),
            }
        )
        return

    replay_with_pyautogui(strokes, config.point_delay, config.stroke_delay, config.driver)


def screen_size() -> tuple[int, int]:
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("pyautogui가 설치되어 있지 않습니다.") from exc
    size = pyautogui.size()
    if size.width <= 0 or size.height <= 0:
        raise RuntimeError(f"유효하지 않은 화면 크기입니다: {size.width}x{size.height}")
    return int(size.width), int(size.height)


def center_from_rect(rect: Rect) -> Point:
    x, y, width, height = rect
    return x + width / 2.0, y + height / 2.0


def send_hotkey(hotkey: str) -> None:
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("pyautogui가 설치되어 있지 않습니다.") from exc

    aliases = {"cmd": "command"}
    keys = [aliases.get(part.strip().lower(), part.strip().lower()) for part in hotkey.split("+") if part.strip()]
    if not keys:
        raise RuntimeError("단축키가 비어 있습니다.")
    pyautogui.hotkey(*keys)
    time.sleep(0.2)


def select_pen(config: ControllerConfig, skip_pen_select: bool) -> None:
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("pyautogui가 설치되어 있지 않습니다.") from exc

    pyautogui.PAUSE = 0.1
    if skip_pen_select:
        print("WARN: --skip_pen_select 때문에 펜 선택 클릭을 생략합니다.")
        return

    if config.tool_select_mode == "hotkey":
        send_hotkey(config.pen_hotkey)
        return

    if config.pen_button_point is None:
        raise RuntimeError("펜 버튼 좌표가 없습니다. --pen_point x,y 또는 config 설정이 필요합니다.")

    pyautogui.click(*config.pen_button_point)
    time.sleep(0.2)
    if config.black_color_point is not None:
        pyautogui.click(*config.black_color_point)
        time.sleep(0.2)
    else:
        print("WARN: 검은색 버튼 좌표가 없어 색상 선택 클릭을 생략합니다.")


def select_lasso(config: ControllerConfig) -> None:
    if config.tool_select_mode != "hotkey":
        raise RuntimeError("올가미 선택은 현재 hotkey 모드만 지원합니다.")
    send_hotkey(config.lasso_hotkey)


def interpolate_path(vertices: list[Point], point_count: int) -> list[Point]:
    point_count = max(point_count, len(vertices))
    segments = list(zip(vertices, vertices[1:]))
    lengths = [math.dist(start, end) for start, end in segments]
    total_length = max(sum(lengths), 1.0)
    points = [vertices[0]]
    for (start, end), length in zip(segments, lengths):
        steps = max(1, round(point_count * length / total_length))
        for index in range(1, steps + 1):
            ratio = index / steps
            points.append(
                (
                    start[0] + (end[0] - start[0]) * ratio,
                    start[1] + (end[1] - start[1]) * ratio,
                )
            )
    return points


def rectangle_lasso_path(rect: Rect, point_count: int, close_overlap: float) -> list[Point]:
    x, y, width, height = rect
    left, top = x, y
    right, bottom = x + width, y + height
    top_mid = (left + width / 2.0, top)
    overlap = min(max(close_overlap, 0.0), width / 3.0)
    vertices = [
        top_mid,
        (right, top),
        (right, bottom),
        (left, bottom),
        (left, top),
        top_mid,
        (top_mid[0] + overlap, top),
    ]
    return interpolate_path(vertices, point_count)


def ellipse_lasso_path(rect: Rect, point_count: int, close_overlap: float) -> list[Point]:
    x, y, width, height = rect
    center_x, center_y = x + width / 2.0, y + height / 2.0
    radius_x, radius_y = width / 2.0, height / 2.0
    point_count = max(point_count, 24)
    average_radius = max((radius_x + radius_y) / 2.0, 1.0)
    overlap_angle = max(close_overlap, 0.0) / average_radius
    total_angle = math.tau + overlap_angle
    start_angle = -math.pi / 2.0
    return [
        (
            center_x + math.cos(start_angle + total_angle * index / point_count) * radius_x,
            center_y + math.sin(start_angle + total_angle * index / point_count) * radius_y,
        )
        for index in range(point_count + 1)
    ]


def build_lasso_path(config: ControllerConfig, rect: Rect) -> list[Point]:
    if config.lasso_shape == "ellipse":
        return ellipse_lasso_path(rect, config.lasso_point_count, config.lasso_close_overlap)
    return rectangle_lasso_path(rect, config.lasso_point_count, config.lasso_close_overlap)


def drag_lasso_rect(rect: Rect, config: ControllerConfig) -> None:
    points = build_lasso_path(config, rect)
    if config.input_backend == "quartz":
        run_quartz_payload(
            {
                "kind": "drag_path",
                "points": points,
                "drag_duration": max(config.lasso_drag_duration, 0.0),
                "mouse_down_delay": max(config.quartz_mouse_down_delay, 0.0),
            }
        )
        return

    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("pyautogui가 설치되어 있지 않습니다.") from exc

    segment_duration = max(config.lasso_drag_duration, 0.0) / max(len(points) - 1, 1)

    pyautogui.PAUSE = 0
    pyautogui.FAILSAFE = True
    pyautogui.moveTo(*points[0], duration=0.1)
    pyautogui.mouseDown(button="left")
    try:
        for point in points[1:]:
            raise_if_aborted()
            if config.lasso_driver == "drag":
                pyautogui.dragTo(
                    *point,
                    duration=segment_duration,
                    button="left",
                    mouseDownUp=False,
                )
            else:
                pyautogui.moveTo(*point, duration=segment_duration)
    finally:
        pyautogui.mouseUp(button="left")


def copy_with_lasso(config: ControllerConfig, selection_rect: Rect) -> None:
    select_lasso(config)
    time.sleep(max(config.lasso_tool_delay, 0.0))
    drag_lasso_rect(selection_rect, config)
    time.sleep(max(config.copy_delay, 0.0))
    attempts = max(config.copy_retries, 1)
    for index in range(attempts):
        raise_if_aborted()
        send_hotkey(config.copy_hotkey)
        if index < attempts - 1:
            time.sleep(max(config.copy_retry_delay, 0.0))


def draw_horizontal_line(center: Point, length: float, driver: str) -> tuple[Point, Point]:
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("pyautogui가 설치되어 있지 않습니다.") from exc

    pyautogui.PAUSE = 0
    pyautogui.FAILSAFE = True
    half = max(length, 1.0) / 2.0
    start = (center[0] - half, center[1])
    end = (center[0] + half, center[1])

    pyautogui.moveTo(*start, duration=0.1)
    if driver == "drag":
        pyautogui.dragTo(*end, duration=0.35, button="left")
    else:
        pyautogui.mouseDown(button="left")
        try:
            pyautogui.moveTo(*end, duration=0.35)
        finally:
            pyautogui.mouseUp(button="left")
    return start, end


def main() -> None:
    args = parse_args()
    raw_config = load_json_config(args.config)
    config = controller_config(raw_config, args)
    strokes_path = resolve_path(args.strokes) if args.strokes else None
    mapped_strokes = prepare_mapped_strokes(strokes_path, config) if strokes_path else None
    selection_rect = padded_rect(stroke_bbox(mapped_strokes), config.lasso_padding) if mapped_strokes else None
    if args.copy_after_draw and mapped_strokes is None:
        raise RuntimeError("--copy_after_draw는 --strokes 모드에서만 사용할 수 있습니다.")
    if mapped_strokes is None:
        explicit_center = parse_point(args.line_center)
        width, height = screen_size()
        if explicit_center is not None:
            line_center = explicit_center
        elif config.paper_rect is not None:
            line_center = center_from_rect(config.paper_rect)
        else:
            line_center = None
        if line_center is None:
            line_center = (width / 2.0, height / 2.0)
    else:
        width = height = None
        line_center = None

    if width is not None and height is not None:
        print(f"screen: {width}x{height}")
    else:
        print("screen: skipped for strokes mode")
    print(f"pen point: {config.pen_button_point}")
    print(f"black color point: {config.black_color_point}")
    print(f"paper rect: {config.paper_rect}")
    print(f"target rect: {config.target_rect}")
    print(f"tool select mode: {config.tool_select_mode}")
    print(f"pen hotkey: {config.pen_hotkey}")
    print(f"lasso hotkey: {config.lasso_hotkey}")
    if line_center is not None:
        print(f"line center: {tuple(round(v, 2) for v in line_center)}")
    print(f"line length: {config.line_length}")
    print(f"input backend: {config.input_backend}")
    print(f"driver: {config.driver}")
    if mapped_strokes is not None:
        print(f"draw mode: strokes")
        print(f"strokes path: {strokes_path}")
        print(f"fit: {config.fit}")
        print(f"sample step: {config.sample_step}")
        print(f"min point distance: {config.min_point_distance}")
        print(f"point delay: {config.point_delay}")
        print(f"stroke delay: {config.stroke_delay}")
        print(f"quartz point delay: {config.quartz_point_delay}")
        print(f"quartz stroke delay: {config.quartz_stroke_delay}")
        print(f"quartz mouse down delay: {config.quartz_mouse_down_delay}")
        print(f"quartz post draw delay: {config.quartz_post_draw_delay}")
        if selection_rect is not None:
            print(f"copy after draw: {args.copy_after_draw}")
            print(f"lasso selection rect: {tuple(round(v, 2) for v in selection_rect)}")
            print(f"lasso driver: {config.lasso_driver}")
            print(f"lasso shape: {config.lasso_shape}")
            print(f"lasso point count: {config.lasso_point_count}")
            print(f"lasso close overlap: {config.lasso_close_overlap}")
            print(f"lasso padding: {config.lasso_padding}")
            print(f"lasso drag duration: {config.lasso_drag_duration}")
            print(f"lasso tool delay: {config.lasso_tool_delay}")
            print(f"copy hotkey: {config.copy_hotkey}")
            print(f"copy delay: {config.copy_delay}")
            print(f"copy retries: {config.copy_retries}")
            print(f"copy retry delay: {config.copy_retry_delay}")
    else:
        print("draw mode: test_line")

    if not args.execute:
        print("dry-run: 실제 GoodNotes 조작은 실행하지 않았습니다. --execute를 붙이면 실행됩니다.")
        return

    install_abort_handlers()
    app_name = activate_goodnotes()
    if not args.skip_fullscreen:
        set_goodnotes_fullscreen(app_name)
    frontmost = require_frontmost_goodnotes()
    print(f"frontmost: {frontmost}")
    select_pen(config, args.skip_pen_select)
    action = "strokes.json 입력" if mapped_strokes is not None else "중앙 테스트 선 입력"
    print(f"{config.countdown:.1f}초 후 {action}을 시작합니다.")
    time.sleep(max(config.countdown, 0.0))
    try:
        if mapped_strokes is not None:
            replay_strokes_with_backend(mapped_strokes, config)
            if args.copy_after_draw and selection_rect is not None:
                if config.input_backend == "quartz":
                    time.sleep(max(config.quartz_post_draw_delay, 0.0))
                copy_with_lasso(config, selection_rect)
                print("copied with lasso")
        else:
            start, end = draw_horizontal_line(line_center, config.line_length, config.driver)
            print(f"line start: {tuple(round(v, 2) for v in start)}")
            print(f"line end: {tuple(round(v, 2) for v in end)}")
        if args.select_lasso_after_draw:
            select_lasso(config)
            print("lasso selected")
    except KeyboardInterrupt:
        print("사용자 인터럽트로 GoodNotes 자동 입력을 중단했습니다.")
        sys.exit(130)
    print("done")


if __name__ == "__main__":
    main()
