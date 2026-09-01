"""
Zhang-Suen 스켈레톤화 결과 시각화 도구
======================================
원본 / binary / skeleton / overlay / 특수점 / 메트릭을 한 번에 점검합니다.
"""

import argparse
import os
import sys

import cv2
import matplotlib

# 기본은 저장/검증에 안전한 Agg를 사용하고, 필요할 때만 GUI를 켭니다.
if os.environ.get("SKELETONIZER_GUI") == "1" and matplotlib.get_backend().lower() == "agg":
    matplotlib.use('TkAgg')
else:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from skeletonizer import load_and_preprocess, skeletonize_zhang


def count_branch_points(skeleton):
    """스켈레톤에서 분기점 수를 계산합니다."""
    skel = (skeleton > 0).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    kernel[1, 1] = 0
    neighbor_count = cv2.filter2D(skel, -1, kernel)
    return int(np.sum((skel == 1) & (neighbor_count >= 3)))


def count_end_points(skeleton):
    """스켈레톤에서 끝점 수를 계산합니다."""
    skel = (skeleton > 0).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    kernel[1, 1] = 0
    neighbor_count = cv2.filter2D(skel, -1, kernel)
    return int(np.sum((skel == 1) & (neighbor_count == 1)))


def analyze_skeleton(skeleton, binary):
    """시각화용 기본 메트릭을 계산합니다."""
    skel_pixels = int(np.sum(skeleton > 0))
    orig_pixels = int(np.sum(binary > 0))
    num_labels, _ = cv2.connectedComponents(skeleton)
    return {
        "skeleton_pixels": skel_pixels,
        "original_pixels": orig_pixels,
        "compression_ratio": (skel_pixels / orig_pixels) if orig_pixels > 0 else 0,
        "connected_components": int(num_labels - 1),
        "branch_points": count_branch_points(skeleton),
        "end_points": count_end_points(skeleton),
    }


def create_overlay(original_bgr, skeleton, color=(0, 255, 0), thickness=3):
    """원본 이미지 위에 skeleton을 오버레이합니다."""
    overlay = original_bgr.copy()
    if thickness == 1:
        overlay[skeleton > 0] = color
        return overlay

    skel_dilated = cv2.dilate(
        (skeleton > 0).astype(np.uint8),
        np.ones((thickness, thickness), np.uint8),
    )
    overlay[skel_dilated > 0] = color
    return overlay


def create_overlay_with_points(original_bgr, skeleton, thickness=3, point_size=5):
    """분기점과 끝점을 함께 표시한 오버레이를 생성합니다."""
    overlay = create_overlay(original_bgr, skeleton, thickness=thickness)
    skel = (skeleton > 0).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    kernel[1, 1] = 0
    neighbor_count = cv2.filter2D(skel, -1, kernel)

    branch_y, branch_x = np.where((skel == 1) & (neighbor_count >= 3))
    for y, x in zip(branch_y, branch_x):
        cv2.circle(overlay, (x, y), point_size, (0, 0, 255), -1)

    end_y, end_x = np.where((skel == 1) & (neighbor_count == 1))
    for y, x in zip(end_y, end_x):
        cv2.circle(overlay, (x, y), point_size, (255, 0, 0), -1)

    return overlay


def visualize_skeleton(image_path, save_path=None, thickness=3, point_size=5):
    """Zhang-Suen 결과를 2x3 패널로 시각화합니다."""
    img, gray, binary = load_and_preprocess(image_path)
    skeleton, elapsed, method_name = skeletonize_zhang(binary)

    overlay = create_overlay(img, skeleton, thickness=thickness)
    overlay_with_points = create_overlay_with_points(
        img, skeleton, thickness=thickness, point_size=point_size
    )
    metrics = analyze_skeleton(skeleton, binary)

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(f"Skeletonizer: {os.path.basename(image_path)}", fontsize=14, fontweight="bold")

    axes[0, 0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axes[0, 0].set_title("Original Image")
    axes[0, 0].axis("off")

    axes[0, 1].imshow(binary, cmap="gray")
    axes[0, 1].set_title("Binary (preprocessed)")
    axes[0, 1].axis("off")

    axes[0, 2].imshow(skeleton, cmap="gray")
    axes[0, 2].set_title(f"{method_name}\n(elapsed: {elapsed * 1000:.1f}ms)")
    axes[0, 2].axis("off")

    axes[1, 0].imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    axes[1, 0].set_title("Skeleton Overlay")
    axes[1, 0].axis("off")

    axes[1, 1].imshow(cv2.cvtColor(overlay_with_points, cv2.COLOR_BGR2RGB))
    axes[1, 1].set_title("Branch(Red) & End(Blue) Points")
    axes[1, 1].axis("off")

    metrics_text = (
        f"Method: {method_name}\n"
        f"Processing Time: {elapsed * 1000:.1f} ms\n\n"
        f"Original Pixels: {metrics['original_pixels']:,}\n"
        f"Skeleton Pixels: {metrics['skeleton_pixels']:,}\n"
        f"Compression Ratio: {metrics['compression_ratio']:.4f}\n\n"
        f"Connected Components: {metrics['connected_components']}\n"
        f"Branch Points: {metrics['branch_points']}\n"
        f"End Points: {metrics['end_points']}"
    )
    axes[1, 2].axis("off")
    axes[1, 2].text(
        0.1,
        0.5,
        metrics_text,
        transform=axes[1, 2].transAxes,
        fontsize=11,
        verticalalignment="center",
        fontfamily="monospace",
        bbox=dict(boxstyle="round,pad=0.8", facecolor="lightyellow", alpha=0.8),
    )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"결과 저장: {save_path}")

    if matplotlib.get_backend().lower() == "agg":
        plt.close(fig)
    else:
        plt.show()


def select_file_dialog():
    """파일 선택 다이얼로그를 엽니다."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            title="글자 이미지를 선택하세요",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif"),
                ("All files", "*.*"),
            ],
        )
        root.destroy()
        return file_path if file_path else None
    except Exception as exc:
        print(f"파일 선택 다이얼로그 오류: {exc}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Zhang-Suen skeletonizer 시각화 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python skeletonizer_visualize.py
  python skeletonizer_visualize.py --input image.png
  python skeletonizer_visualize.py --input image.png --save
        """,
    )
    parser.add_argument("--input", "-i", type=str, help="입력 이미지 경로")
    parser.add_argument("--save", "-s", action="store_true", help="결과 이미지 저장")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="결과 이미지 저장 경로 (기본: 입력파일명_skeleton_overview.png)",
    )
    parser.add_argument("--thickness", "-t", type=int, default=3, help="스켈레톤 라인 두께")
    parser.add_argument("--point_size", type=int, default=5, help="분기점/끝점 표시 크기")
    args = parser.parse_args()

    image_path = args.input
    if image_path is None:
        image_path = select_file_dialog()
        if image_path is None:
            print("파일이 선택되지 않았습니다.")
            sys.exit(0)

    if not os.path.exists(image_path):
        print(f"파일을 찾을 수 없습니다: {image_path}")
        sys.exit(1)

    save_path = None
    if args.save or args.output:
        base, _ = os.path.splitext(image_path)
        save_path = args.output or f"{base}_skeleton_overview.png"

    visualize_skeleton(
        image_path,
        save_path=save_path,
        thickness=args.thickness,
        point_size=args.point_size,
    )


if __name__ == "__main__":
    main()
