import turtle
import time
import argparse
import sys
import os
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 화면 없이 파일로 저장
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager

# Windows 한글 폰트 설정
def _set_korean_font():
    candidates = ['Malgun Gothic', 'NanumGothic', 'AppleGothic', 'NanumBarunGothic']
    for name in candidates:
        if any(name.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
            plt.rcParams['font.family'] = name
            return
    # 폴백: 맑은 고딕 경로 직접 등록
    mgothic = r'C:\Windows\Fonts\malgun.ttf'
    if os.path.exists(mgothic):
        font_manager.fontManager.addfont(mgothic)
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=mgothic).get_name()

_set_korean_font()

# 기존 모듈 임포트
from skeletonizer import load_and_preprocess, skeletonize_zhang
from stroke_extractor import extract_strokes, STROKE_COLORS, STROKE_COLORS_BGR

def save_result_image(strokes, img, save_path):
    """3패널 결과 이미지를 저장합니다.

    [패널 1] 원본 이미지
    [패널 2] 원본 + 획 오버레이  (획별 색상, 시작점 작은 도트만 표시)
    [패널 3] 복원 이미지         (흰 배경에 획별 색상으로만 표시)
    """
    h, w = img.shape[:2]
    orig_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if len(img.shape) == 3 \
               else cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

    # ── 패널 2: 원본 위에 획 오버레이 ──
    # 원본을 약간 밝게 처리해 획이 잘 보이도록
    base_overlay = cv2.addWeighted(orig_rgb, 0.45,
                                   np.ones_like(orig_rgb) * 255, 0.55, 0)
    thickness_ov = max(2, int(max(w, h) * 0.006))
    for i, stroke in enumerate(strokes):
        if len(stroke) == 0:
            continue
        bgr = STROKE_COLORS_BGR[i % len(STROKE_COLORS_BGR)]
        color_rgb = (bgr[2], bgr[1], bgr[0])
        pts = stroke.astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(base_overlay, [pts], isClosed=False, color=color_rgb,
                      thickness=thickness_ov, lineType=cv2.LINE_AA)
        # 시작점만 작은 도트로 표시
        sx, sy = int(stroke[0][0]), int(stroke[0][1])
        r = thickness_ov + 2
        cv2.circle(base_overlay, (sx, sy), r, color_rgb, -1, lineType=cv2.LINE_AA)
        cv2.circle(base_overlay, (sx, sy), r + 1, (255, 255, 255), 1, lineType=cv2.LINE_AA)

    # ── 패널 3: 복원 이미지 (흰 배경 + 색상 획) ──
    restored = np.ones((h, w, 3), dtype=np.uint8) * 255
    thickness_re = max(2, int(max(w, h) * 0.007))
    for i, stroke in enumerate(strokes):
        if len(stroke) == 0:
            continue
        bgr = STROKE_COLORS_BGR[i % len(STROKE_COLORS_BGR)]
        color_rgb = (bgr[2], bgr[1], bgr[0])
        pts = stroke.astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(restored, [pts], isClosed=False, color=color_rgb,
                      thickness=thickness_re, lineType=cv2.LINE_AA)
        # 시작점 작은 도트
        sx, sy = int(stroke[0][0]), int(stroke[0][1])
        r = thickness_re + 1
        cv2.circle(restored, (sx, sy), r, color_rgb, -1, lineType=cv2.LINE_AA)

    # ── matplotlib 3패널 배치 ──
    fig_w = max(14, w / 40)
    fig_h = max(5,  h / 40)
    fig, axes = plt.subplots(1, 3, figsize=(fig_w, fig_h), dpi=120)

    axes[0].imshow(orig_rgb)
    axes[0].set_title("원본 이미지", fontsize=11)
    axes[0].axis('off')

    axes[1].imshow(base_overlay)
    axes[1].set_title(f"원본 + 획 오버레이  ({len(strokes)}획)", fontsize=11)
    axes[1].axis('off')

    axes[2].imshow(restored)
    axes[2].set_title("복원 이미지 (획 구분)", fontsize=11)
    axes[2].axis('off')

    plt.tight_layout(pad=1.5)
    plt.savefig(save_path, bbox_inches='tight', dpi=120)
    plt.close(fig)
    print(f"결과 이미지 저장 완료: {save_path}")


def save_black_strokes_image(strokes, img, save_path):
    """모든 획을 검은색으로 그린 이미지를 저장합니다 (색 구분 없음)."""
    h, w = img.shape[:2]
    canvas = np.ones((h, w, 3), dtype=np.uint8) * 255
    thickness = max(2, int(max(w, h) * 0.007))
    for stroke in strokes:
        if len(stroke) == 0:
            continue
        pts = stroke.astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(canvas, [pts], isClosed=False, color=(0, 0, 0),
                      thickness=thickness, lineType=cv2.LINE_AA)
    # BGR → RGB for matplotlib
    fig, ax = plt.subplots(1, 1, figsize=(max(6, w / 100), max(6, h / 100)), dpi=120)
    ax.imshow(canvas)
    ax.axis('off')
    plt.tight_layout(pad=0.5)
    plt.savefig(save_path, bbox_inches='tight', dpi=120)
    plt.close(fig)
    print(f"흑백 획 이미지 저장 완료: {save_path}")


def draw_strokes_with_turtle(strokes, img_width, img_height, speed=0):
    """
    Turtle 모듈을 사용하여 추출된 획(Stroke)들을 애니메이션으로 랜더링합니다.

    창 크기는 모니터 해상도에 맞게 자동 축소되며, 좌표도 같은 비율로 스케일됩니다.
    """
    import tkinter as _tk
    # ── 모니터 해상도 조회 후 창 크기 결정 ──
    _root = _tk.Tk()
    _root.withdraw()
    screen_w = _root.winfo_screenwidth()
    screen_h = _root.winfo_screenheight()
    _root.destroy()

    MAX_W = int(screen_w * 0.85)
    MAX_H = int(screen_h * 0.85)

    scale = min(MAX_W / img_width, MAX_H / img_height, 1.0)
    win_w = int(img_width  * scale)
    win_h = int(img_height * scale)

    screen = turtle.Screen()
    screen.setup(width=win_w + 20, height=win_h + 20)
    screen.title("스마트 아카이브 - 자동 필기 시뮬레이션")
    screen.bgcolor("white")

    # Turtle 초기화
    pen = turtle.Turtle()
    pen.speed(0)       # turtle 자체 speed는 항상 최대 — 부드러움은 tracer로 제어
    pen.pensize(max(1, int(2 * scale)))
    pen.hideturtle()

    # 좌표계 변환: 이미지(좌상단 원점, y↓) → Turtle(중앙 원점, y↑), 스케일 적용
    def to_turtle_coords(x, y):
        tx = (x - img_width  / 2) * scale
        ty = (img_height / 2 - y) * scale
        return tx, ty

    # ── tracer 설정 ──
    # speed=0 : 획 단위로 한꺼번에 그린 뒤 update → 거의 순간 완성
    # speed>0 : 1틱마다 화면 갱신 → 획이 실시간으로 그려지는 모습 표시
    if speed == 0:
        screen.tracer(0)   # 자동 업데이트 OFF
    else:
        screen.tracer(1)   # 매 틱마다 갱신 (애니메이션 가시)

    for i, stroke in enumerate(strokes):
        if len(stroke) == 0:
            continue

        color_hex = STROKE_COLORS[i % len(STROKE_COLORS)]
        pen.color(color_hex)
        pen.penup()
        pen.goto(to_turtle_coords(*stroke[0]))
        pen.pendown()

        # 점 샘플링: speed>0 이면 보기 좋게 촘촘히, speed=0 이면 더 성기게
        step = max(1, len(stroke) // 80) if speed > 0 else max(1, len(stroke) // 20)
        for p_idx in range(1, len(stroke), step):
            pen.goto(to_turtle_coords(*stroke[p_idx]))
        pen.goto(to_turtle_coords(*stroke[-1]))  # 마지막 점 보장

        pen.penup()

        if speed == 0:
            screen.update()   # 획 하나 완성 후 화면에 반영

    screen.update()
    print("그리기 완료! 화면을 클릭하면 종료됩니다.")
    try:
        screen.exitonclick()
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description='Turtle을 이용한 필기 애니메이션 시연')
    parser.add_argument('--input', '-i', type=str, required=True, help='입력 이미지 경로')
    parser.add_argument('--speed', '-s', type=int, default=0, help='그리기 속도 (1~10, 0은 최고속도)')
    parser.add_argument('--save', action='store_true', help='결과 이미지 저장')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='3패널 컬러 결과 이미지 저장 경로 (기본: 입력파일명_result.png)')
    parser.add_argument('--output_black', type=str, default=None,
                        help='흑백 획 이미지 저장 경로 (기본: 입력파일명_strokes_black.png)')
    parser.add_argument('--no_turtle', action='store_true', help='Turtle 애니메이션 없이 저장만 수행')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print("파일이 존재하지 않습니다.")
        sys.exit(1)

    print(f"[{args.input}] 획 추출 중...")
    img, gray, binary = load_and_preprocess(args.input)
    h, w = img.shape[:2]

    skeleton, _, _ = skeletonize_zhang(binary)
    strokes = extract_strokes(skeleton, image_gray=gray)
    print(f"총 {len(strokes)}가닥의 획을 그립니다!")

    # 결과 이미지 저장
    if args.save or args.output or args.output_black or args.no_turtle:
        base = os.path.splitext(os.path.basename(args.input))[0]
        out_dir = os.path.dirname(args.input) or '.'

        save_path = args.output or os.path.join(out_dir, f"{base}_result.png")
        black_path = args.output_black or os.path.join(out_dir, f"{base}_strokes_black.png")

        save_result_image(strokes, img, save_path)
        save_black_strokes_image(strokes, img, black_path)

    # Turtle 애니메이션
    if not args.no_turtle:
        draw_strokes_with_turtle(strokes, w, h, speed=args.speed)

if __name__ == '__main__':
    main()
