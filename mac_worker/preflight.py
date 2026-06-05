from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOODNOTES_APP_CANDIDATES = (
    "/Applications/Goodnotes.app",
    "/Applications/GoodNotes.app",
)
GOODNOTES_PROCESS_NAMES = ("Goodnotes", "GoodNotes")


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    required: bool = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GoodNotes replay 워커 실행 전 로컬 환경과 설정을 점검합니다."
    )
    parser.add_argument("--config", default="mac_worker/config.json", help="워커 설정 JSON 경로")
    parser.add_argument("--strokes", default=None, help="dry-run으로 확인할 strokes.json 경로")
    parser.add_argument(
        "--require-goodnotes-running",
        action="store_true",
        help="GoodNotes 프로세스 실행 여부를 필수 조건으로 검사합니다.",
    )
    parser.add_argument(
        "--require-display",
        action="store_true",
        help="pyautogui가 0보다 큰 화면 크기를 읽어야 통과하도록 검사합니다.",
    )
    parser.add_argument(
        "--require-frontmost-goodnotes",
        action="store_true",
        help="GoodNotes가 현재 전면 앱이어야 통과하도록 검사합니다.",
    )
    parser.add_argument(
        "--check-swift",
        action="store_true",
        help="dump_goodnotes_clipboard.swift의 Swift typecheck를 수행합니다.",
    )
    parser.add_argument("--json", action="store_true", help="결과를 JSON으로 출력합니다.")
    return parser.parse_args()


def resolve_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


def load_config(path: str) -> dict[str, Any]:
    config_path = resolve_path(path)
    return json.loads(config_path.read_text(encoding="utf-8"))


def parse_rect(value: str) -> tuple[float, float, float, float]:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("target_rect는 x,y,width,height 형식이어야 합니다.")
    x, y, width, height = parts
    if width <= 0 or height <= 0:
        raise ValueError("target_rect width/height는 0보다 커야 합니다.")
    return x, y, width, height


def check_config(config: dict[str, Any]) -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        rect = parse_rect(str(config["target_rect"]))
        results.append(CheckResult("target_rect", True, f"{tuple(round(v, 2) for v in rect)}"))
    except Exception as exc:
        results.append(CheckResult("target_rect", False, str(exc)))

    mode = config.get("mode", "mock")
    results.append(CheckResult("mode", mode in {"mock", "replay"}, str(mode)))

    execute = bool(config.get("execute_goodnotes_writer", False))
    detail = "실제 마우스 입력 활성화" if execute else "dry-run 모드"
    results.append(CheckResult("execute_goodnotes_writer", True, detail, required=False))

    pasteboard_type = config.get("pasteboard_type")
    expected = "com.goodnotesapp.goodnotes5.notes"
    results.append(
        CheckResult(
            "pasteboard_type",
            pasteboard_type == expected,
            str(pasteboard_type),
        )
    )
    return results


def check_pyautogui(require_display: bool) -> CheckResult:
    if importlib.util.find_spec("pyautogui") is None:
        return CheckResult("pyautogui", False, "pyautogui가 설치되어 있지 않습니다.")
    try:
        import pyautogui

        size = pyautogui.size()
        if size.width <= 0 or size.height <= 0:
            return CheckResult(
                "pyautogui display",
                False,
                f"screen={size.width}x{size.height}; 실제 입력 전 표시 장치 접근을 확인해야 합니다.",
                required=require_display,
            )
        return CheckResult("pyautogui", True, f"installed, screen={size.width}x{size.height}")
    except Exception as exc:
        return CheckResult("pyautogui", False, f"import 또는 screen 확인 실패: {exc}")


def check_goodnotes_app() -> CheckResult:
    found = [path for path in GOODNOTES_APP_CANDIDATES if Path(path).exists()]
    if found:
        return CheckResult("GoodNotes app", True, found[0])
    return CheckResult(
        "GoodNotes app",
        False,
        "Applications 아래에서 Goodnotes.app 또는 GoodNotes.app을 찾지 못했습니다.",
    )


def check_goodnotes_running(required: bool) -> CheckResult:
    if platform.system() != "Darwin":
        return CheckResult("GoodNotes process", False, "macOS가 아닙니다.", required=required)
    for name in GOODNOTES_PROCESS_NAMES:
        result = subprocess.run(
            ["pgrep", "-x", name],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            pids = ",".join(result.stdout.split())
            return CheckResult("GoodNotes process", True, f"{name} pid={pids}", required=required)
    return CheckResult("GoodNotes process", False, "실행 중인 GoodNotes 프로세스를 찾지 못했습니다.", required=required)


def check_frontmost_goodnotes(required: bool) -> CheckResult:
    if platform.system() != "Darwin":
        return CheckResult("frontmost app", False, "macOS가 아닙니다.", required=required)
    result = subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to get name of first application process whose frontmost is true',
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return CheckResult("frontmost app", False, detail, required=required)
    frontmost = result.stdout.strip()
    ok = frontmost in GOODNOTES_PROCESS_NAMES
    return CheckResult("frontmost app", ok, frontmost or "unknown", required=required)


def check_swift_typecheck() -> CheckResult:
    if shutil.which("swiftc") is None:
        return CheckResult("Swift typecheck", False, "swiftc를 찾지 못했습니다.")
    env = os.environ.copy()
    env.setdefault("CLANG_MODULE_CACHE_PATH", "/private/tmp/h2i_clang_module_cache")
    swift_files = [
        "mac_worker/dump_goodnotes_clipboard.swift",
        "mac_worker/goodnotes_quartz_replay.swift",
    ]
    for swift_file in swift_files:
        result = subprocess.run(
            ["swiftc", "-typecheck", swift_file],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            return CheckResult("Swift typecheck", False, f"{swift_file}: {detail}")
    return CheckResult("Swift typecheck", True, "Swift worker scripts typecheck 통과")


def check_strokes(path: str | None) -> CheckResult:
    if not path:
        return CheckResult("strokes.json", True, "검사 생략", required=False)
    strokes_path = resolve_path(path)
    try:
        data = json.loads(strokes_path.read_text(encoding="utf-8"))
        raw_strokes = data.get("strokes", data if isinstance(data, list) else [])
        stroke_count = len(raw_strokes)
        point_count = 0
        for raw in raw_strokes:
            points = raw.get("global_points") if isinstance(raw, dict) else raw
            point_count += len(points or [])
        if stroke_count <= 0 or point_count <= 0:
            raise ValueError("사용 가능한 stroke point가 없습니다.")
        return CheckResult("strokes.json", True, f"strokes={stroke_count}, points={point_count}")
    except Exception as exc:
        return CheckResult("strokes.json", False, str(exc))


def print_text(results: list[CheckResult]) -> None:
    for result in results:
        marker = "OK" if result.ok else ("WARN" if not result.required else "FAIL")
        print(f"[{marker}] {result.name}: {result.detail}")


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    results: list[CheckResult] = []
    results.extend(check_config(config))
    results.append(check_pyautogui(require_display=args.require_display))
    results.append(check_goodnotes_app())
    results.append(check_goodnotes_running(required=args.require_goodnotes_running))
    results.append(check_frontmost_goodnotes(required=args.require_frontmost_goodnotes))
    results.append(check_strokes(args.strokes))
    if args.check_swift:
        results.append(check_swift_typecheck())

    if args.json:
        print(json.dumps([result.__dict__ for result in results], ensure_ascii=False, indent=2))
    else:
        print_text(results)

    failed = [result for result in results if result.required and not result.ok]
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
