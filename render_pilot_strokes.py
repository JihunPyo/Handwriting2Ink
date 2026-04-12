import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".mplconfig"))
os.environ.setdefault("XDG_CACHE_HOME", str(PROJECT_ROOT / ".xdg_cache"))

from simulate_drawing import save_black_strokes_image, save_result_image
from skeletonizer import load_and_preprocess, skeletonize_zhang
from stroke_extractor import extract_strokes


def parse_args():
    parser = argparse.ArgumentParser(
        description="OCR pilot text crop들을 stroke로 변환한 뒤 원래 위치에 맞춰 전체 캔버스에 렌더링합니다."
    )
    parser.add_argument(
        "--pilot_dir",
        required=True,
        help="pilot_outputs/<name> 디렉토리 경로",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="3패널 결과 이미지 경로 (기본: <pilot_dir>/crop_stroke_composite_result.png)",
    )
    parser.add_argument(
        "--output_black",
        default=None,
        help="흑백 stroke 이미지 경로 (기본: <pilot_dir>/crop_stroke_composite_black.png)",
    )
    return parser.parse_args()


def load_regions(pilot_dir: Path):
    data = json.loads((pilot_dir / "regions.json").read_text(encoding="utf-8"))
    regions = [
        region
        for region in data["regions"]
        if region["type"] == "text" and region["source"] == "ocr_merged"
    ]
    return data, regions


def resolve_input_image(input_path_value: str) -> Path:
    raw_path = Path(input_path_value)
    candidates = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.append(PROJECT_ROOT / raw_path)
        candidates.append(PROJECT_ROOT / "images" / "inputs" / raw_path.name)

    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"원본 입력 이미지를 찾을 수 없습니다: {input_path_value}")


def load_reference_image(data: dict) -> np.ndarray:
    input_path = resolve_input_image(data["input_path"])
    image = cv2.imread(str(input_path))
    if image is None:
        raise FileNotFoundError(f"원본 입력 이미지를 읽을 수 없습니다: {input_path}")

    scale = float(data.get("scale", 1.0))
    if scale < 0.999:
        image = cv2.resize(
            image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_AREA,
        )
    return image


def extract_crop_strokes(crop_path: Path):
    crop_image = cv2.imread(str(crop_path))
    if crop_image is None:
        raise FileNotFoundError(f"crop 이미지를 읽을 수 없습니다: {crop_path}")
    _, gray, binary = load_and_preprocess(crop_image)
    skeleton, _, _ = skeletonize_zhang(binary)
    return extract_strokes(skeleton, image_gray=gray)


def offset_strokes(strokes, bbox):
    x, y, _, _ = bbox
    offset = np.array([x, y], dtype=np.int32)
    shifted = []
    for stroke in strokes:
        if len(stroke) == 0:
            continue
        shifted.append(stroke.astype(np.int32) + offset)
    return shifted


def main():
    args = parse_args()
    pilot_dir = Path(args.pilot_dir)
    if not pilot_dir.exists():
        raise FileNotFoundError(f"pilot 디렉토리가 없습니다: {pilot_dir}")

    data, text_regions = load_regions(pilot_dir)
    reference_image = load_reference_image(data)

    all_shifted_strokes = []
    summary = []
    for index, region in enumerate(text_regions, start=1):
        crop_path = pilot_dir / "crops" / f"text_{index:03d}.png"
        bbox = region["bbox"]
        strokes = extract_crop_strokes(crop_path)
        shifted_strokes = offset_strokes(strokes, bbox)
        all_shifted_strokes.extend(shifted_strokes)
        summary.append(
            {
                "index": index,
                "bbox": bbox,
                "crop_path": str(crop_path),
                "stroke_count": len(shifted_strokes),
            }
        )
        print(
            f"[region {index:02d}] bbox={bbox} local_strokes={len(strokes)} shifted_strokes={len(shifted_strokes)}"
        )

    output_path = (
        Path(args.output)
        if args.output
        else pilot_dir / "crop_stroke_composite_result.png"
    )
    output_black_path = (
        Path(args.output_black)
        if args.output_black
        else pilot_dir / "crop_stroke_composite_black.png"
    )

    save_result_image(all_shifted_strokes, reference_image, str(output_path))
    save_black_strokes_image(
        all_shifted_strokes,
        reference_image,
        str(output_black_path),
        thickness=1,
    )

    summary_path = pilot_dir / "crop_stroke_composite_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "pilot_dir": str(pilot_dir),
                "input_path": data["input_path"],
                "scale": data.get("scale", 1.0),
                "text_region_count": len(text_regions),
                "total_stroke_count": len(all_shifted_strokes),
                "regions": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"text region count: {len(text_regions)}")
    print(f"total shifted stroke count: {len(all_shifted_strokes)}")
    print(f"summary saved: {summary_path}")


if __name__ == "__main__":
    main()
