from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = PROJECT_ROOT / "backend" / "pipeline"
for import_root in (PROJECT_ROOT, PIPELINE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from render_strokes import (
    collect_target_crop_specs,
    load_reference_image,
    load_regions,
    preprocess_crop_spec,
)
from simulate_drawing import save_black_strokes_image, save_result_image
from skeletonizer import load_and_preprocess, skeletonize_zhang
from stroke_extractor import (
    build_skeleton_graph,
    extract_strokes,
    find_special_points,
    split_into_connected_components,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poster analysis for OCR crop preprocessing effect."
    )
    parser.add_argument(
        "--source",
        default="output/poster_crop_analysis/source_original.jpeg",
        help="Original input image used for whole-image direct processing.",
    )
    parser.add_argument(
        "--pilot_dir",
        default="output/poster_crop_analysis/pipeline",
        help="Pipeline output directory containing regions.json and crop outputs.",
    )
    parser.add_argument(
        "--output_dir",
        default="output/poster_crop_analysis",
        help="Directory where analysis artifacts are written.",
    )
    parser.add_argument(
        "--region_source",
        default="ocr_merged",
        choices=("ocr_merged", "ocr_raw"),
        help="Region source to evaluate for OCR crop processing.",
    )
    parser.add_argument(
        "--crop_scale",
        type=float,
        default=2.0,
        help="Actual pipeline crop scale to include as a reference row.",
    )
    return parser.parse_args()


def count_segments_after_branch_removal(graph, component_pixels, branch_points) -> int:
    remaining = set(component_pixels) - set(branch_points)
    visited = set()
    count = 0

    for start in sorted(remaining):
        if start in visited:
            continue
        count += 1
        stack = [start]
        visited.add(start)
        while stack:
            node = stack.pop()
            for neighbor in graph[node]:
                if neighbor in remaining and neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
    return count


def path_length(stroke: np.ndarray) -> float:
    if len(stroke) < 2:
        return 0.0
    diffs = np.diff(stroke.astype(np.float32), axis=0)
    return float(np.sqrt((diffs**2).sum(axis=1)).sum())


def compute_metrics(
    label: str,
    image_area_px: int,
    processed_area_px: int,
    binary: np.ndarray,
    skeleton: np.ndarray,
    gray: np.ndarray,
) -> tuple[dict, list[np.ndarray]]:
    graph, pixel_set = build_skeleton_graph(skeleton)
    components = split_into_connected_components(graph, pixel_set) if pixel_set else []

    endpoint_count = 0
    branch_count = 0
    raw_segment_count = 0
    for component_graph, component_pixels in components:
        end_points, branch_points = find_special_points(component_graph)
        endpoint_count += len(end_points)
        branch_count += len(branch_points)
        raw_segment_count += count_segments_after_branch_removal(
            component_graph,
            component_pixels,
            branch_points,
        )

    with contextlib.redirect_stdout(io.StringIO()):
        strokes = extract_strokes(skeleton, image_gray=gray)

    point_count = int(sum(len(stroke) for stroke in strokes))
    total_path = float(sum(path_length(stroke) for stroke in strokes))
    foreground_px = int(np.count_nonzero(binary))
    skeleton_px = int(np.count_nonzero(skeleton))

    row = {
        "label": label,
        "image_area_px": int(image_area_px),
        "processed_area_px": int(processed_area_px),
        "processed_area_ratio": processed_area_px / image_area_px if image_area_px else 0.0,
        "foreground_px": foreground_px,
        "foreground_density": foreground_px / processed_area_px if processed_area_px else 0.0,
        "skeleton_px": skeleton_px,
        "skeleton_density": skeleton_px / processed_area_px if processed_area_px else 0.0,
        "connected_components": int(len(components)),
        "endpoints": int(endpoint_count),
        "branch_points": int(branch_count),
        "raw_segments": int(raw_segment_count),
        "stroke_count": int(len(strokes)),
        "point_count": point_count,
        "path_length_px": total_path,
    }
    return row, strokes


def aggregate_rows(label: str, image_area_px: int, rows: list[dict]) -> dict:
    processed_area_px = sum(row["processed_area_px"] for row in rows)
    row = {
        "label": label,
        "image_area_px": int(image_area_px),
        "processed_area_px": int(processed_area_px),
        "processed_area_ratio": processed_area_px / image_area_px if image_area_px else 0.0,
    }

    sum_fields = [
        "foreground_px",
        "skeleton_px",
        "connected_components",
        "endpoints",
        "branch_points",
        "raw_segments",
        "stroke_count",
        "point_count",
        "path_length_px",
    ]
    for field in sum_fields:
        row[field] = sum(item[field] for item in rows)

    row["foreground_density"] = (
        row["foreground_px"] / processed_area_px if processed_area_px else 0.0
    )
    row["skeleton_density"] = (
        row["skeleton_px"] / processed_area_px if processed_area_px else 0.0
    )
    return row


def bbox_union_area(shape: tuple[int, int], specs) -> int:
    height, width = shape
    mask = np.zeros((height, width), dtype=np.uint8)
    for spec in specs:
        x, y, w, h = [int(value) for value in spec["bbox"]]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(width, x + w), min(height, y + h)
        if x0 < x1 and y0 < y1:
            mask[y0:y1, x0:x1] = 1
    return int(mask.sum())


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "label",
        "image_area_px",
        "processed_area_px",
        "processed_area_ratio",
        "foreground_px",
        "foreground_density",
        "skeleton_px",
        "skeleton_density",
        "connected_components",
        "endpoints",
        "branch_points",
        "raw_segments",
        "stroke_count",
        "point_count",
        "path_length_px",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fmt_int(value: float) -> str:
    return f"{int(round(value)):,}"


def fmt_float(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def reduction(before: float, after: float) -> float:
    if before == 0:
        return 0.0
    return (before - after) / before * 100.0


def write_markdown(
    path: Path,
    source: Path,
    pilot_dir: Path,
    rows: list[dict],
    region_count: int,
    union_area: int,
) -> None:
    whole = rows[0]
    crop_same = rows[1]
    crop_actual = rows[2]

    lines = [
        "# OCR Crop 전처리 효과 정량 분석",
        "",
        "## 분석 기준",
        f"- 입력 이미지: `{source}`",
        f"- OCR/pipeline 산출물: `{pilot_dir}`",
        f"- OCR merged crop 수: {region_count}",
        (
            f"- OCR crop bbox union area: {fmt_int(union_area)} px "
            f"({fmt_float(union_area / whole['image_area_px'] * 100, 1)}% of image)"
        ),
        "- 공정 비교용 수치는 crop_scale=1.0 기준으로 산출했다.",
        "- 실제 pipeline 참고값은 crop_scale=2.0 기준으로 별도 행에 기록했다.",
        "",
        "## 결과 표",
        "",
        "| 처리 방식 | 처리 영역 비율 | 전경 픽셀 | 스켈레톤 픽셀 | 연결 성분 | 끝점 | 교차점 | raw segment | 최종 stroke |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {label} | {area_ratio}% | {fg} | {skel} | {comp} | {end} | {branch} | {seg} | {stroke} |".format(
                label=row["label"],
                area_ratio=fmt_float(row["processed_area_ratio"] * 100, 1),
                fg=fmt_int(row["foreground_px"]),
                skel=fmt_int(row["skeleton_px"]),
                comp=fmt_int(row["connected_components"]),
                end=fmt_int(row["endpoints"]),
                branch=fmt_int(row["branch_points"]),
                seg=fmt_int(row["raw_segments"]),
                stroke=fmt_int(row["stroke_count"]),
            )
        )

    lines.extend(
        [
            "",
            "## 포스터용 해석",
            (
                f"- 동일 해상도 기준 OCR crop 처리 영역은 전체 이미지 대비 "
                f"{fmt_float(crop_same['processed_area_ratio'] * 100, 1)}%이다."
            ),
            (
                f"- 전체 이미지 직접 처리 대비 OCR crop 처리에서 전경 픽셀은 "
                f"{fmt_float(reduction(whole['foreground_px'], crop_same['foreground_px']), 1)}% 감소했다."
            ),
            (
                f"- 전체 이미지 직접 처리 대비 OCR crop 처리에서 스켈레톤 픽셀은 "
                f"{fmt_float(reduction(whole['skeleton_px'], crop_same['skeleton_px']), 1)}% 감소했다."
            ),
            (
                f"- 전체 이미지 직접 처리 대비 OCR crop 처리에서 raw segment 후보는 "
                f"{fmt_float(reduction(whole['raw_segments'], crop_same['raw_segments']), 1)}% 감소했다."
            ),
            (
                f"- 실제 pipeline은 crop_scale=2.0을 적용해 최종 {fmt_int(crop_actual['stroke_count'])}개 "
                "stroke를 생성했다. 이 행은 품질 향상을 위한 확대 처리 효과가 포함되어 있으므로, "
                "전처리 절감률 계산에는 사용하지 않았다."
            ),
            "",
            "## 포스터 문구 예시",
            "> OCR 기반 crop을 적용하면 전체 이미지 배경을 직접 스켈레톤화할 때 발생하는 불필요한 전경과 segment 후보가 줄어들어, stroke 추출 단계의 입력 그래프가 더 작고 안정적으로 구성된다.",
            "",
            "## 생성 산출물",
            "- `crop_effect_metrics.csv`: 정량 지표 원본 표",
            "- `whole_direct_stroke_result.png`: 전체 이미지 직접 처리 stroke 시각화",
            "- `whole_direct_binary.png`: 전체 이미지 직접 처리 이진화 결과",
            "- `whole_direct_skeleton.png`: 전체 이미지 직접 처리 스켈레톤 결과",
            "- `pipeline/layout_overlay.png`: OCR crop 영역 시각화",
            "- `pipeline/crop_stroke_composite_result.png`: OCR crop 기반 최종 stroke 시각화",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    pilot_dir = Path(args.pilot_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image, gray, binary = load_and_preprocess(str(source))
    skeleton, _, _ = skeletonize_zhang(binary)
    image_area = int(image.shape[0] * image.shape[1])
    whole_row, whole_strokes = compute_metrics(
        "Whole image direct",
        image_area,
        image_area,
        binary,
        skeleton,
        gray,
    )

    cv2.imwrite(str(output_dir / "whole_direct_binary.png"), 255 - binary)
    cv2.imwrite(str(output_dir / "whole_direct_skeleton.png"), 255 - skeleton)
    save_result_image(
        whole_strokes,
        image,
        str(output_dir / "whole_direct_stroke_result.png"),
    )
    save_black_strokes_image(
        whole_strokes,
        image,
        str(output_dir / "whole_direct_black.png"),
    )

    data, _ = load_regions(pilot_dir, args.region_source)
    reference_image = load_reference_image(data)
    specs = collect_target_crop_specs(data, pilot_dir, args.region_source)
    union_area = bbox_union_area(reference_image.shape[:2], specs)

    crop_rows_same_scale = []
    crop_rows_actual_scale = []
    for spec in specs:
        _, _, crop_gray_1, crop_binary_1, crop_skeleton_1 = preprocess_crop_spec(
            spec,
            reference_image,
            1.0,
        )
        crop_area_1 = int(crop_binary_1.shape[0] * crop_binary_1.shape[1])
        row_1, _ = compute_metrics(
            f"crop_{spec['index']}_scale1",
            image_area,
            crop_area_1,
            crop_binary_1,
            crop_skeleton_1,
            crop_gray_1,
        )
        crop_rows_same_scale.append(row_1)

        _, _, crop_gray_actual, crop_binary_actual, crop_skeleton_actual = preprocess_crop_spec(
            spec,
            reference_image,
            args.crop_scale,
        )
        crop_area_actual = int(crop_binary_actual.shape[0] * crop_binary_actual.shape[1])
        row_actual, _ = compute_metrics(
            f"crop_{spec['index']}_scale{args.crop_scale:g}",
            image_area,
            crop_area_actual,
            crop_binary_actual,
            crop_skeleton_actual,
            crop_gray_actual,
        )
        crop_rows_actual_scale.append(row_actual)

    rows = [
        whole_row,
        aggregate_rows("OCR crop only (scale=1.0)", image_area, crop_rows_same_scale),
        aggregate_rows(
            f"OCR crop only (pipeline scale={args.crop_scale:g})",
            image_area,
            crop_rows_actual_scale,
        ),
    ]

    write_csv(output_dir / "crop_effect_metrics.csv", rows)
    write_csv(output_dir / "crop_effect_metrics_by_crop.csv", crop_rows_same_scale)
    write_markdown(
        output_dir / "crop_effect_analysis.md",
        source,
        pilot_dir,
        rows,
        len(specs),
        union_area,
    )
    print(f"metrics saved: {output_dir / 'crop_effect_metrics.csv'}")
    print(f"analysis saved: {output_dir / 'crop_effect_analysis.md'}")


if __name__ == "__main__":
    main()
