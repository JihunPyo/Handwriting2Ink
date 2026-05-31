from __future__ import annotations

import argparse
import subprocess
import time


Point = tuple[float, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GoodNotes target_rect 캘리브레이션을 위해 절대 화면 좌표로 짧은 선을 입력합니다."
    )
    parser.add_argument(
        "--line",
        required=True,
        help="절대 화면 좌표 x1,y1,x2,y2 예) 700,520,920,520",
    )
    parser.add_argument("--driver", choices=("drag", "down_move"), default="down_move")
    parser.add_argument("--duration", type=float, default=0.8, help="선 입력 시간")
    parser.add_argument("--countdown", type=float, default=5.0, help="실제 입력 전 대기 시간")
    parser.add_argument(
        "--require_frontmost_goodnotes",
        action="store_true",
        help="실제 입력 직전 GoodNotes가 전면 앱인지 확인합니다.",
    )
    parser.add_argument(
        "--activate_goodnotes",
        action="store_true",
        help="실제 입력 전에 GoodNotes 앱을 전면으로 올립니다.",
    )
    parser.add_argument("--execute", action="store_true", help="실제 마우스 입력을 수행합니다.")
    return parser.parse_args()


def parse_line(value: str) -> tuple[Point, Point]:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("--line은 x1,y1,x2,y2 형식이어야 합니다.")
    x1, y1, x2, y2 = parts
    return (x1, y1), (x2, y2)


def require_frontmost_goodnotes() -> None:
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
        raise RuntimeError(f"전면 앱 확인에 실패했습니다: {detail}")
    frontmost = result.stdout.strip()
    if frontmost not in {"Goodnotes", "GoodNotes"}:
        raise RuntimeError(f"GoodNotes가 전면 앱이 아닙니다: {frontmost}")


def activate_goodnotes() -> None:
    errors = []
    for app_name in ("Goodnotes", "GoodNotes"):
        result = subprocess.run(
            ["osascript", "-e", f'tell application "{app_name}" to activate'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            time.sleep(0.5)
            return
        errors.append((result.stderr or result.stdout).strip())
    raise RuntimeError(f"GoodNotes 활성화에 실패했습니다: {' | '.join(errors)}")


def draw_line(start: Point, end: Point, duration: float, driver: str) -> None:
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("pyautogui가 설치되어 있지 않습니다.") from exc

    pyautogui.PAUSE = 0
    pyautogui.FAILSAFE = True
    x1, y1 = start
    x2, y2 = end
    pyautogui.moveTo(x1, y1, duration=0.1)
    if driver == "drag":
        pyautogui.dragTo(x2, y2, duration=max(duration, 0.0), button="left")
        return

    pyautogui.mouseDown(button="left")
    try:
        pyautogui.moveTo(x2, y2, duration=max(duration, 0.0))
    finally:
        pyautogui.mouseUp(button="left")


def main() -> None:
    args = parse_args()
    start, end = parse_line(args.line)
    print(f"line start: {tuple(round(v, 2) for v in start)}")
    print(f"line end: {tuple(round(v, 2) for v in end)}")
    print(f"driver: {args.driver}")
    if not args.execute:
        print("dry-run: 실제 마우스 입력은 실행하지 않았습니다. --execute를 붙이면 실행됩니다.")
        return

    print(f"{args.countdown:.1f}초 후 절대좌표 선 입력을 시작합니다.")
    if args.activate_goodnotes:
        activate_goodnotes()
    time.sleep(max(0.0, args.countdown))
    if args.require_frontmost_goodnotes:
        require_frontmost_goodnotes()
    draw_line(start, end, args.duration, args.driver)
    print("done")


if __name__ == "__main__":
    main()
