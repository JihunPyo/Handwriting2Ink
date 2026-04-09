"""
Skeletonizer 성능 테스트 프로그램
=================================
글자 이미지를 입력받아 다양한 스켈레톤화 방법을 적용하고,
원본 이미지 위에 스켈레톤을 오버레이하여 결과를 시각화합니다.

사용법:
    python skeletonizer_test.py                    # 파일 선택 다이얼로그
    python skeletonizer_test.py --input image.png  # 특정 이미지 파일
    python skeletonizer_test.py --input_dir ./images  # 폴더 내 모든 이미지
"""

import argparse
import os
import sys
import time
import glob
import numpy as np
import cv2
import matplotlib
if matplotlib.get_backend() == 'agg':  # 이미 다른 백엔드가 설정된 경우 유지
    matplotlib.use('TkAgg')  # GUI 백엔드
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from skimage.morphology import skeletonize, thin, medial_axis
from skimage import img_as_ubyte, img_as_float


# ============================================================
# 1. 이미지 전처리 함수들
# ============================================================

def _order_quad_points(points):
    """사각형 꼭짓점을 좌상, 우상, 우하, 좌하 순으로 정렬합니다."""
    pts = np.array(points, dtype=np.float32)
    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).reshape(-1)
    return np.array([
        pts[np.argmin(sums)],
        pts[np.argmin(diffs)],
        pts[np.argmax(sums)],
        pts[np.argmax(diffs)],
    ], dtype=np.float32)


def _warp_document(image, quad):
    """검출한 문서 사각형을 반듯하게 펴서 잘라냅니다."""
    rect = _order_quad_points(quad.reshape(4, 2))
    tl, tr, br, bl = rect

    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)

    dst_w = max(1, int(max(width_top, width_bottom)))
    dst_h = max(1, int(max(height_left, height_right)))

    dst = np.array([
        [0, 0],
        [dst_w - 1, 0],
        [dst_w - 1, dst_h - 1],
        [0, dst_h - 1],
    ], dtype=np.float32)

    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (dst_w, dst_h))


def _detect_document_region(image):
    """밝은 큰 사각형 문서 영역을 찾아 crop/보정합니다."""
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # 종이는 배경보다 밝으므로 밝은 영역을 우선 후보로 잡습니다.
    _, bright_mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bright_mask = cv2.morphologyEx(
        bright_mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    )

    contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = h * w * 0.15

    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        area = cv2.contourArea(contour)
        if area < min_area:
            continue

        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.03 * perimeter, True)
        if len(approx) == 4:
            return _warp_document(image, approx)

        x, y, cw, ch = cv2.boundingRect(contour)
        aspect = cw / max(ch, 1)
        if 0.5 <= aspect <= 1.8:
            return image[y:y + ch, x:x + cw].copy()

    return image


def _normalize_document_gray(gray):
    """문서 내부 조명/질감 변화를 줄이고 글자를 강조합니다."""
    background = cv2.GaussianBlur(gray, (0, 0), sigmaX=25, sigmaY=25)
    normalized = cv2.divide(gray, background, scale=255)
    normalized = cv2.normalize(normalized, None, 0, 255, cv2.NORM_MINMAX)
    normalized = cv2.medianBlur(normalized, 3)
    return normalized


def _extract_text_mask(gray):
    """흰 종이 위의 어두운 필기를 black-hat 기반으로 추출합니다."""
    norm_gray = _normalize_document_gray(gray)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (19, 19))
    blackhat = cv2.morphologyEx(norm_gray, cv2.MORPH_BLACKHAT, kernel)
    blackhat = cv2.GaussianBlur(blackhat, (3, 3), 0)

    _, otsu = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(
        blackhat, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, -4
    )
    binary = cv2.bitwise_and(otsu, adaptive)

    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, open_kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, close_kernel)
    return binary


def _filter_small_components(binary, min_area_ratio=0.00003):
    """손글씨보다 훨씬 작은 점성 노이즈를 제거합니다."""
    h, w = binary.shape[:2]
    min_area = max(12, int(h * w * min_area_ratio))
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    filtered = np.zeros_like(binary)
    for idx in range(1, num_labels):
        x, y, cw, ch, area = stats[idx]
        if area < min_area:
            continue
        if cw >= int(w * 0.85) or ch >= int(h * 0.85):
            continue
        filtered[labels == idx] = 255

    return filtered


def load_and_preprocess(image_input, target_size=None):
    """이미지를 로드하고 이진화 전처리를 수행합니다.
    (파일 경로 또는 OpenCV BGR numpy 배열 입력 지원)
    """
    if isinstance(image_input, str):
        img = cv2.imread(image_input)
        if img is None:
            raise FileNotFoundError(f"이미지를 로드할 수 없습니다: {image_input}")
    else:
        # image_input이 numpy 배열이라고 가정
        img = image_input.copy()
        
    
    # 크기 조정 (선택적)
    if target_size is not None:
        h, w = img.shape[:2]
        scale = target_size / max(h, w)
        if scale < 1.0:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    # 전체 장면이 아니라 문서 내부만 대상으로 전처리합니다.
    img = _detect_document_region(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    binary = _extract_text_mask(gray)
    binary = _filter_small_components(binary)

    return img, gray, binary


def adaptive_preprocess(image_path, target_size=None):
    """문서 crop + 조명 보정 + adaptive 조합을 포함한 공통 전처리."""
    return load_and_preprocess(image_path, target_size=target_size)


# ============================================================
# 2. 스켈레톤화 방법들
# ============================================================

def method_skeletonize_lee(binary):
    """scikit-image skeletonize (Lee method) - 기본 방법"""
    binary_bool = binary > 0
    start = time.time()
    skeleton = skeletonize(binary_bool, method='lee')
    elapsed = time.time() - start
    return img_as_ubyte(skeleton), elapsed, "Skeletonize (Lee)"


def method_skeletonize_zhang(binary):
    """Zhang-Suen thinning algorithm을 사용한 스켈레톤화"""
    binary_bool = binary > 0
    start = time.time()
    skeleton = skeletonize(binary_bool)
    elapsed = time.time() - start
    return img_as_ubyte(skeleton), elapsed, "Skeletonize (Zhang-Suen)"


def method_thin(binary):
    """scikit-image thin (morphological thinning)"""
    binary_bool = binary > 0
    start = time.time()
    thinned = thin(binary_bool)
    elapsed = time.time() - start
    return img_as_ubyte(thinned), elapsed, "Morphological Thinning"


def method_medial_axis(binary):
    """Medial Axis Transform"""
    binary_bool = binary > 0
    start = time.time()
    skel, distance = medial_axis(binary_bool, return_distance=True)
    elapsed = time.time() - start
    return img_as_ubyte(skel), elapsed, "Medial Axis Transform"


def method_opencv_thinning(binary):
    """OpenCV의 ximgproc thinning (Zhang-Suen)"""
    start = time.time()
    try:
        thinned = cv2.ximgproc.thinning(binary, thinningType=cv2.ximgproc.THINNING_ZHANGSUEN)
    except AttributeError:
        # ximgproc가 없으면 대체 구현 사용
        thinned = _zhang_suen_thinning(binary)
    elapsed = time.time() - start
    return thinned, elapsed, "OpenCV Thinning (Zhang-Suen)"


def _zhang_suen_thinning(binary):
    """Zhang-Suen thinning의 순수 Python 구현 (ximgproc 없을 때 폴백)"""
    img = binary.copy() // 255
    prev = np.zeros(img.shape, np.uint8)
    
    while True:
        # Sub-iteration 1
        marker = np.zeros(img.shape, np.uint8)
        for i in range(1, img.shape[0] - 1):
            for j in range(1, img.shape[1] - 1):
                if img[i, j] != 1:
                    continue
                p2, p3 = img[i-1, j], img[i-1, j+1]
                p4, p5 = img[i, j+1], img[i+1, j+1]
                p6, p7 = img[i+1, j], img[i+1, j-1]
                p8, p9 = img[i, j-1], img[i-1, j-1]
                
                neighbors = [p2, p3, p4, p5, p6, p7, p8, p9]
                B = sum(neighbors)
                
                transitions = 0
                pattern = neighbors + [neighbors[0]]
                for k in range(len(pattern) - 1):
                    if pattern[k] == 0 and pattern[k+1] == 1:
                        transitions += 1
                
                if 2 <= B <= 6 and transitions == 1:
                    if p2 * p4 * p6 == 0 and p4 * p6 * p8 == 0:
                        marker[i, j] = 1
        
        img = img - marker
        
        if np.array_equal(img, prev):
            break
        prev = img.copy()
    
    return img * 255


# ============================================================
# 3. 스켈레톤 좌표 추출 및 분석
# ============================================================

def extract_skeleton_coords(skeleton):
    """스켈레톤에서 좌표를 추출합니다."""
    coords = np.column_stack(np.where(skeleton > 0))
    return coords  # (y, x) 형태


def analyze_skeleton(skeleton, binary):
    """스켈레톤 품질 분석 메트릭을 계산합니다."""
    skel_pixels = np.sum(skeleton > 0)
    orig_pixels = np.sum(binary > 0)
    
    # 압축률 (원본 대비 스켈레톤 픽셀 수)
    compression_ratio = skel_pixels / orig_pixels if orig_pixels > 0 else 0
    
    # 연결 성분 수 (이상적으로 글자 획 수와 비슷)
    num_labels, labels = cv2.connectedComponents(skeleton)
    num_components = num_labels - 1  # 배경 제외
    
    # 분기점 수 (3개 이상의 이웃을 가진 점)
    branch_points = count_branch_points(skeleton)
    
    # 끝점 수 (1개의 이웃만 가진 점)
    end_points = count_end_points(skeleton)
    
    return {
        'skeleton_pixels': skel_pixels,
        'original_pixels': orig_pixels,
        'compression_ratio': compression_ratio,
        'connected_components': num_components,
        'branch_points': branch_points,
        'end_points': end_points,
    }


def count_branch_points(skeleton):
    """스켈레톤에서 분기점(branch point) 수를 세어줍니다."""
    skel = (skeleton > 0).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    kernel[1, 1] = 0
    neighbor_count = cv2.filter2D(skel, -1, kernel)
    branch_points = np.sum((skel == 1) & (neighbor_count >= 3))
    return branch_points


def count_end_points(skeleton):
    """스켈레톤에서 끝점(end point) 수를 세어줍니다."""
    skel = (skeleton > 0).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    kernel[1, 1] = 0
    neighbor_count = cv2.filter2D(skel, -1, kernel)
    end_points = np.sum((skel == 1) & (neighbor_count == 1))
    return end_points


# ============================================================
# 4. 시각화 함수들
# ============================================================

def create_overlay(original_bgr, skeleton, color=(0, 255, 0), thickness=1):
    """원본 이미지 위에 스켈레톤을 오버레이합니다."""
    overlay = original_bgr.copy()
    
    if thickness == 1:
        overlay[skeleton > 0] = color
    else:
        # 두꺼운 스켈레톤 오버레이
        skel_dilated = cv2.dilate(
            (skeleton > 0).astype(np.uint8),
            np.ones((thickness, thickness), np.uint8)
        )
        overlay[skel_dilated > 0] = color
    
    return overlay


def create_overlay_with_points(original_bgr, skeleton, show_branch=True, show_end=True, thickness=3, point_size=5):
    """분기점과 끝점을 표시한 오버레이를 생성합니다."""
    overlay = original_bgr.copy()
    
    # 스켈레톤 (녹색)
    if thickness == 1:
        overlay[skeleton > 0] = (0, 255, 0)
    else:
        skel_dilated = cv2.dilate(
            (skeleton > 0).astype(np.uint8),
            np.ones((thickness, thickness), np.uint8)
        )
        overlay[skel_dilated > 0] = (0, 255, 0)
    
    skel = (skeleton > 0).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    kernel[1, 1] = 0
    neighbor_count = cv2.filter2D(skel, -1, kernel)
    
    # 분기점 (빨간색 원)
    if show_branch:
        branch_y, branch_x = np.where((skel == 1) & (neighbor_count >= 3))
        for y, x in zip(branch_y, branch_x):
            cv2.circle(overlay, (x, y), point_size, (0, 0, 255), -1)
    
    # 끝점 (파란색 원)
    if show_end:
        end_y, end_x = np.where((skel == 1) & (neighbor_count == 1))
        for y, x in zip(end_y, end_x):
            cv2.circle(overlay, (x, y), point_size, (255, 0, 0), -1)
    
    return overlay


def visualize_single_method(image_path, method_func=method_skeletonize_zhang, save_path=None, thickness=3):
    """단일 방법으로 스켈레톤화 결과를 시각화합니다."""
    img, gray, binary = load_and_preprocess(image_path)
    skeleton, elapsed, method_name = method_func(binary)
    
    # 오버레이 생성
    overlay = create_overlay(img, skeleton, color=(0, 255, 0), thickness=thickness)
    overlay_with_points = create_overlay_with_points(img, skeleton, thickness=thickness)
    
    # 분석
    metrics = analyze_skeleton(skeleton, binary)
    
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(f'Skeletonizer Test: {os.path.basename(image_path)}', fontsize=14, fontweight='bold')
    
    # 원본
    axes[0, 0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axes[0, 0].set_title('Original Image')
    axes[0, 0].axis('off')
    
    # 이진화
    axes[0, 1].imshow(binary, cmap='gray')
    axes[0, 1].set_title('Binary (preprocessed)')
    axes[0, 1].axis('off')
    
    # 스켈레톤
    axes[0, 2].imshow(skeleton, cmap='gray')
    axes[0, 2].set_title(f'{method_name}\n(elapsed: {elapsed*1000:.1f}ms)')
    axes[0, 2].axis('off')
    
    # 오버레이 (초록)
    axes[1, 0].imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    axes[1, 0].set_title('Skeleton Overlay (Green)')
    axes[1, 0].axis('off')
    
    # 오버레이 (분기점/끝점 표시)
    axes[1, 1].imshow(cv2.cvtColor(overlay_with_points, cv2.COLOR_BGR2RGB))
    axes[1, 1].set_title('Branch(Red) & End(Blue) Points')
    axes[1, 1].axis('off')
    
    # 메트릭 텍스트
    axes[1, 2].axis('off')
    metrics_text = (
        f"━━━ Analysis Metrics ━━━\n\n"
        f"Method: {method_name}\n"
        f"Processing Time: {elapsed*1000:.1f} ms\n\n"
        f"Original Pixels: {metrics['original_pixels']:,}\n"
        f"Skeleton Pixels: {metrics['skeleton_pixels']:,}\n"
        f"Compression Ratio: {metrics['compression_ratio']:.4f}\n\n"
        f"Connected Components: {metrics['connected_components']}\n"
        f"Branch Points: {metrics['branch_points']}\n"
        f"End Points: {metrics['end_points']}"
    )
    axes[1, 2].text(0.1, 0.5, metrics_text, transform=axes[1, 2].transAxes,
                     fontsize=11, verticalalignment='center', fontfamily='monospace',
                     bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', alpha=0.8))
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"결과 저장: {save_path}")
    
    plt.show()


def visualize_comparison(image_path, save_path=None, thickness=3):
    """모든 스켈레톤화 방법을 비교하여 시각화합니다."""
    img, gray, binary = load_and_preprocess(image_path)
    
    methods = [
        method_skeletonize_zhang,
        method_skeletonize_lee,
        method_thin,
        method_medial_axis,
    ]
    
    # OpenCV ximgproc 확인
    try:
        cv2.ximgproc.thinning
        methods.append(method_opencv_thinning)
    except AttributeError:
        pass
    
    results = []
    for method in methods:
        skeleton, elapsed, name = method(binary)
        metrics = analyze_skeleton(skeleton, binary)
        overlay = create_overlay(img, skeleton, color=(0, 255, 0), thickness=thickness)
        results.append({
            'skeleton': skeleton,
            'elapsed': elapsed,
            'name': name,
            'metrics': metrics,
            'overlay': overlay,
        })
    
    n_methods = len(results)
    fig = plt.figure(figsize=(6 * n_methods, 14))
    fig.suptitle(
        f'Skeletonizer 방법 비교: {os.path.basename(image_path)}',
        fontsize=16, fontweight='bold', y=0.98
    )
    
    gs = GridSpec(3, n_methods, figure=fig, hspace=0.3, wspace=0.2)
    
    for i, result in enumerate(results):
        # Row 1: 스켈레톤
        ax1 = fig.add_subplot(gs[0, i])
        ax1.imshow(result['skeleton'], cmap='gray')
        ax1.set_title(f"{result['name']}\n({result['elapsed']*1000:.1f}ms)", fontsize=10)
        ax1.axis('off')
        
        # Row 2: 오버레이
        ax2 = fig.add_subplot(gs[1, i])
        ax2.imshow(cv2.cvtColor(result['overlay'], cv2.COLOR_BGR2RGB))
        ax2.set_title('Overlay', fontsize=10)
        ax2.axis('off')
        
        # Row 3: 메트릭
        ax3 = fig.add_subplot(gs[2, i])
        ax3.axis('off')
        m = result['metrics']
        text = (
            f"Pixels: {m['skeleton_pixels']:,}\n"
            f"Ratio: {m['compression_ratio']:.4f}\n"
            f"Components: {m['connected_components']}\n"
            f"Branches: {m['branch_points']}\n"
            f"Endpoints: {m['end_points']}"
        )
        ax3.text(0.5, 0.5, text, transform=ax3.transAxes,
                 fontsize=9, verticalalignment='center', horizontalalignment='center',
                 fontfamily='monospace',
                 bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.8))
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"비교 결과 저장: {save_path}")
    
    plt.show()
    
    # 요약 출력
    print("\n" + "=" * 70)
    print(f"{'Method':<30} {'Time(ms)':>10} {'Pixels':>10} {'Branches':>10} {'Endpoints':>10}")
    print("=" * 70)
    for r in results:
        m = r['metrics']
        print(f"{r['name']:<30} {r['elapsed']*1000:>10.1f} {m['skeleton_pixels']:>10,} "
              f"{m['branch_points']:>10} {m['end_points']:>10}")
    print("=" * 70)


def visualize_overlay_only(image_path, save_path=None, thickness=3):
    """원본 이미지 위에 스켈레톤만 오버레이하여 보여줍니다. (가장 간단한 출력)"""
    img, gray, binary = load_and_preprocess(image_path)
    skeleton, elapsed, method_name = method_skeletonize_zhang(binary)
    
    # 오버레이 생성
    overlay = create_overlay(img, skeleton, color=(0, 255, 0), thickness=thickness)
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    fig.suptitle(f'Skeletonizer Result: {os.path.basename(image_path)}', fontsize=14, fontweight='bold')
    
    axes[0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axes[0].set_title('Original')
    axes[0].axis('off')
    
    axes[1].imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    axes[1].set_title(f'Skeleton Overlay ({method_name}, {elapsed*1000:.1f}ms)')
    axes[1].axis('off')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"결과 저장: {save_path}")
    
    plt.show()


def save_overlay_image(image_path, output_path=None, thickness=3):
    """스켈레톤 오버레이 이미지를 파일로 저장합니다."""
    img, gray, binary = load_and_preprocess(image_path)
    skeleton, elapsed, method_name = method_skeletonize_zhang(binary)
    
    overlay = create_overlay(img, skeleton, color=(0, 255, 0), thickness=thickness)
    
    if output_path is None:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_skeleton{ext}"
    
    cv2.imwrite(output_path, overlay)
    print(f"오버레이 이미지 저장: {output_path}")
    return output_path


# ============================================================
# 5. 메인 실행
# ============================================================

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
                ("All files", "*.*")
            ]
        )
        root.destroy()
        return file_path if file_path else None
    except Exception as e:
        print(f"파일 선택 다이얼로그 오류: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Skeletonizer 성능 테스트 프로그램',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python skeletonizer_test.py                               # 파일 선택 다이얼로그
  python skeletonizer_test.py --input image.png             # 단일 이미지
  python skeletonizer_test.py --input image.png --compare   # 방법 비교
  python skeletonizer_test.py --input_dir ./images          # 폴더 내 모든 이미지
  python skeletonizer_test.py --input image.png --save      # 결과 저장
        """
    )
    parser.add_argument('--input', '-i', type=str, help='입력 이미지 경로')
    parser.add_argument('--input_dir', '-d', type=str, help='이미지 폴더 경로 (폴더 내 모든 이미지 처리)')
    parser.add_argument('--compare', '-c', action='store_true', help='모든 방법 비교')
    parser.add_argument('--save', '-s', action='store_true', help='결과 이미지 저장')
    parser.add_argument('--output_dir', '-o', type=str, default='./results', help='결과 저장 경로 (기본: ./results)')
    parser.add_argument('--simple', action='store_true', help='간단한 오버레이만 표시')
    parser.add_argument('--thickness', '-t', type=int, default=3, help='스켈레톤 라인 두께 (기본: 3)')
    
    args = parser.parse_args()
    
    # 이미지 경로 결정
    image_paths = []
    
    if args.input_dir:
        exts = ['*.png', '*.jpg', '*.jpeg', '*.bmp', '*.tiff', '*.tif']
        for ext in exts:
            image_paths.extend(glob.glob(os.path.join(args.input_dir, ext)))
        if not image_paths:
            print(f"폴더에서 이미지를 찾을 수 없습니다: {args.input_dir}")
            sys.exit(1)
        image_paths.sort()
        print(f"{len(image_paths)}개의 이미지를 찾았습니다.")
    elif args.input:
        if not os.path.exists(args.input):
            print(f"파일을 찾을 수 없습니다: {args.input}")
            sys.exit(1)
        image_paths = [args.input]
    else:
        # 파일 선택 다이얼로그
        path = select_file_dialog()
        if path is None:
            print("파일이 선택되지 않았습니다.")
            sys.exit(0)
        image_paths = [path]
    
    # 결과 저장 디렉토리
    if args.save:
        os.makedirs(args.output_dir, exist_ok=True)
    
    # 각 이미지 처리
    for idx, image_path in enumerate(image_paths):
        print(f"\n[{idx+1}/{len(image_paths)}] 처리 중: {image_path}")
        
        try:
            save_path = None
            if args.save:
                basename = os.path.splitext(os.path.basename(image_path))[0]
                save_path = os.path.join(args.output_dir, f"{basename}_result.png")
            
            if args.simple:
                visualize_overlay_only(image_path, save_path=save_path, thickness=args.thickness)
            elif args.compare:
                visualize_comparison(image_path, save_path=save_path, thickness=args.thickness)
            else:
                visualize_single_method(image_path, save_path=save_path, thickness=args.thickness)
            
            # 오버레이 이미지도 저장
            if args.save:
                save_overlay_image(image_path, 
                    os.path.join(args.output_dir, f"{basename}_overlay.png"),
                    thickness=args.thickness)
                
        except Exception as e:
            print(f"오류 발생: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print("\n완료!")


if __name__ == '__main__':
    main()
