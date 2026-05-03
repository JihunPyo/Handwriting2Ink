"""Top-level OCR-to-stroke pipeline orchestrator.

This module intentionally keeps the existing stage implementations separate.
It runs the OCR layout stage first, then renders OCR text crops as strokes.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OCR layout 생성부터 crop stroke 합성까지 한 번에 실행합니다."
    )
    parser.add_argument("--input", required=True, help="입력 이미지 경로")
    parser.add_argument(
        "--output_dir",
        default=None,
        help="OCR layout/stroke 결과 디렉토리 (기본: pilot_outputs/<입력파일명>)",
    )
    parser.add_argument(
        "--resize_max",
        type=int,
        default=1600,
        help="OCR layout 단계의 긴 변 기준 최대 리사이즈 길이. 0 이하면 원본 유지",
    )
    parser.add_argument(
        "--skip_layout",
        action="store_true",
        help="이미 생성된 regions.json/crops를 사용하고 OCR layout 단계는 건너뜁니다.",
    )
    parser.add_argument(
        "--skip_render",
        action="store_true",
        help="OCR layout만 실행하고 stroke 렌더링 단계는 건너뜁니다.",
    )
    parser.add_argument(
        "--layout_debug",
        action="store_true",
        help="ocr_layout.py의 debug 산출물을 저장합니다.",
    )
    parser.add_argument(
        "--region_source",
        choices=("ocr_merged", "ocr_raw"),
        default="ocr_merged",
        help="render_strokes.py에서 사용할 text region 소스. shape region은 항상 함께 포함됩니다.",
    )
    parser.add_argument(
        "--crop_scale",
        type=float,
        default=2.0,
        help="render_strokes.py에서 crop별 skeletonize 전에 적용할 확대 배율",
    )
    parser.add_argument(
        "--black_thickness",
        type=int,
        default=1,
        help="흑백 stroke 이미지의 선 두께",
    )
    parser.add_argument(
        "--result_thickness",
        type=int,
        default=None,
        help="3패널 결과 이미지의 컬러 stroke 선 두께",
    )
    parser.add_argument(
        "--save_crop_debug",
        action="store_true",
        help="crop별 scaled crop/binary/skeleton/overlay를 저장합니다.",
    )
    parser.add_argument(
        "--crop_debug_mode",
        choices=("text", "all"),
        default="text",
        help="crop debug 대상: text 또는 all(text+shape)",
    )
    parser.add_argument(
        "--save_merged_debug",
        action="store_true",
        help="crop 병합 canvas와 병합 기준 전처리/stroke 결과를 저장합니다.",
    )
    parser.add_argument(
        "--merged_debug_mode",
        choices=("text", "all"),
        default="text",
        help="merged debug 대상: text 또는 all(text+shape)",
    )
    parser.add_argument(
        "--save_stroke_data",
        action="store_true",
        help="최종 stroke 좌표열 JSON을 저장합니다.",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="실행하지 않고 호출할 하위 명령만 출력합니다.",
    )
    return parser.parse_args()


def resolve_output_dir(input_path: Path, output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir)
    return PROJECT_ROOT / "pilot_outputs" / input_path.stem


def build_layout_command(args: argparse.Namespace, input_path: Path, output_dir: Path) -> list[str]:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "ocr_layout.py"),
        "--input",
        str(input_path),
        "--output_dir",
        str(output_dir),
        "--resize_max",
        str(args.resize_max),
        "--save_crops",
    ]
    if args.layout_debug:
        command.append("--debug")
    return command


def build_render_command(args: argparse.Namespace, output_dir: Path) -> list[str]:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "render_strokes.py"),
        "--pilot_dir",
        str(output_dir),
        "--region_source",
        args.region_source,
        "--crop_scale",
        str(args.crop_scale),
        "--black_thickness",
        str(args.black_thickness),
    ]
    if args.result_thickness is not None:
        command.extend(["--result_thickness", str(args.result_thickness)])
    if args.save_crop_debug:
        command.extend(["--save_crop_debug", "--crop_debug_mode", args.crop_debug_mode])
    if args.save_merged_debug:
        command.extend([
            "--save_merged_debug",
            "--merged_debug_mode",
            args.merged_debug_mode,
        ])
    if args.save_stroke_data:
        command.append("--save_stroke_data")
    return command


def run_command(command: list[str], dry_run: bool) -> None:
    printable = " ".join(command)
    print(f"[pipeline] $ {printable}")
    if dry_run:
        return
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = resolve_output_dir(input_path, args.output_dir)

    if not args.skip_layout and not input_path.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {input_path}")
    if args.skip_layout and not output_dir.exists():
        raise FileNotFoundError(f"기존 OCR layout 출력 디렉토리가 없습니다: {output_dir}")

    print(f"[pipeline] input: {input_path}")
    print(f"[pipeline] output_dir: {output_dir}")

    if not args.skip_layout:
        run_command(build_layout_command(args, input_path, output_dir), args.dry_run)
    else:
        print("[pipeline] OCR layout 단계 건너뜀")

    if not args.skip_render:
        run_command(build_render_command(args, output_dir), args.dry_run)
    else:
        print("[pipeline] stroke rendering 단계 건너뜀")

    print("[pipeline] done")


if __name__ == "__main__":
    main()
