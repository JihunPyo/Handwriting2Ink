# Handwriting2Ink

손글씨 또는 손그림 문서 이미지에서 전경을 추출하고, skeleton 기반 stroke 좌표열로 변환해 다시 그려 보는 실험 프로젝트입니다.

현재 `main`은 두 흐름을 포함합니다.

- 기본 파이프라인: 이미지 전체를 전처리한 뒤 Zhang-Suen skeletonize와 stroke extraction을 수행합니다.
- OCR 파일럿: PaddleOCR로 text/shape 영역을 crop하고, text crop별 stroke를 원래 이미지 좌표계에 다시 배치합니다.

---

## 1. 환경

Python 실행은 conda `DV` 환경을 기준으로 합니다.

```bash
conda run -n DV python <script.py> ...
```

OCR 파일럿에는 다음 패키지가 필요합니다.

```bash
conda run -n DV python -m pip install "numpy<2"
conda run -n DV python -m pip install paddlepaddle==3.2.0
conda run -n DV python -m pip install paddleocr==3.2.0
```

PaddleOCR 모델/cache는 프로젝트 로컬의 `.paddlex_cache/`, `.mplconfig/`, `.xdg_cache/`에 저장되며 Git에는 포함하지 않습니다.

---

## 2. 기본 파이프라인

```text
입력 이미지
  -> load_and_preprocess
  -> Zhang-Suen skeletonize
  -> skeleton graph 구성
  -> branch/end point 기반 segment 분리
  -> 연속성 기반 stroke 병합
  -> stroke 좌표열 렌더링
```

실행 예시:

```bash
conda run -n DV python simulate_drawing.py \
  --input images/inputs/test_heojw.jpeg \
  --save \
  --no_turtle
```

출력:

- `<input>_result.png`: 원본, stroke overlay, 색상 복원 3패널
- `<input>_strokes_black.png`: 흰 배경 위 검은 stroke 결과

---

## 3. OCR Layout 파일럿

`ocr_layout.py`는 PaddleOCR mobile 모델로 text bbox를 찾고, text mask를 제외한 전경에서 shape 후보를 분리합니다.

실행 예시:

```bash
conda run -n DV python ocr_layout.py \
  --input images/inputs/H2I_flowchart.jpeg \
  --save_crops \
  --debug
```

주요 출력:

- `pilot_outputs/<입력명>/layout_overlay.png`
- `pilot_outputs/<입력명>/text_mask.png`
- `pilot_outputs/<입력명>/shape_mask.png`
- `pilot_outputs/<입력명>/regions.json`
- `pilot_outputs/<입력명>/crops/text_*.png`
- `pilot_outputs/<입력명>/crops/shape_*.png`

현재 OCR 결과의 인식 문자열은 저장하지만, stroke 생성 판단에는 bbox와 polygon 좌표만 사용합니다.

---

## 4. OCR Crop Stroke 합성

`render_strokes.py`는 OCR 파일럿 결과의 `ocr_merged` text crop을 각각 stroke로 변환한 뒤, 각 crop의 bbox offset을 더해 원본 이미지 위치에 다시 배치합니다.

기본 실행:

```bash
conda run -n DV python render_strokes.py \
  --pilot_dir pilot_outputs/H2I_flowchart \
  --crop_scale 2.0 \
  --black_thickness 2
```

디버그 포함 실행:

```bash
conda run -n DV python render_strokes.py \
  --pilot_dir pilot_outputs/H2I_flowchart \
  --crop_scale 2.0 \
  --black_thickness 2 \
  --result_thickness 2 \
  --save_crop_debug \
  --save_merged_debug \
  --save_stroke_data
```

주요 옵션:

| 옵션 | 설명 |
|---|---|
| `--crop_scale` | crop별 skeletonize 전에 이미지를 확대합니다. 기본값은 `2.0`입니다. |
| `--black_thickness` | 흑백 stroke 결과의 선 두께입니다. |
| `--result_thickness` | 3패널 컬러 결과의 stroke 선 두께입니다. |
| `--save_crop_debug` | crop별 scaled crop, binary, skeleton, overlay를 저장합니다. |
| `--save_merged_debug` | crop들을 원위치에 붙인 canvas와 그 canvas 기준 전처리/stroke 결과를 저장합니다. |
| `--save_stroke_data` | crop-local 좌표와 global 좌표를 JSON으로 저장합니다. |

주의: 실제 기본 경로는 “crop별로 따로 전처리/스켈레톤화/stroke 추출 후 좌표만 원래 위치로 이동”입니다. `--save_merged_debug`는 비교용이며, 병합된 crop canvas를 다시 전처리하면 crop 배경이 전경으로 잡힐 수 있습니다.

---

## 5. Skeletonizer 시각화

`skeletonizer_visualize.py`는 단일 이미지의 전처리, binary, skeleton, overlay, 특수점 정보를 빠르게 확인하는 도구입니다.

```bash
conda run -n DV python skeletonizer_visualize.py \
  --input images/inputs/test_heojw.jpeg \
  --save
```

---

## 6. 주요 파일

| 파일 | 역할 |
|---|---|
| `skeletonizer.py` | 이미지 로드, 전처리, Zhang-Suen skeletonize |
| `stroke_extractor.py` | skeleton graph 분석 및 stroke 좌표열 추출 |
| `simulate_drawing.py` | 기본 파이프라인 실행, 결과 이미지 저장, Turtle 애니메이션 |
| `skeletonizer_visualize.py` | skeletonizer 결과 시각화 CLI |
| `ocr_layout.py` | OCR 기반 text/shape layout 분리 파일럿 |
| `render_strokes.py` | OCR text crop별 stroke 추출 후 원위치 합성 |
| `commit_log.md` | 실험/변경 기록 |

---

## 7. Git 관리 정책

Git에는 코드와 최소 디렉토리 구조만 포함합니다. 테스트 이미지, 생성 이미지, OCR 산출물, 캐시는 로컬 전용입니다.

무시되는 대표 항목:

- `*.png`, `*.jpg`, `*.jpeg`, `*.bmp`, `*.tiff`, `*.tif`
- `pilot_outputs/`
- `.paddlex_cache/`
- `.mplconfig/`
- `.xdg_cache/`
- `AGENTS.md`
- `*.md` 단, `README.md`와 `commit_log.md`는 추적

---

## 8. 현재 한계

- Skeleton 기반 stroke는 글자의 중심선만 남기므로, 사람 눈에 읽기 좋은 글자 모양 복원과는 다릅니다.
- OCR crop을 너무 크게 병합하면 글자와 화살표/도형이 같은 graph로 처리되어 stroke가 과도하게 분할될 수 있습니다.
- `--crop_scale`은 작은 글씨의 픽셀 손실 완화에는 도움이 되지만, branch point 기반 segmentation 문제 자체를 해결하지는 않습니다.
- OCR 파일럿은 아직 production pipeline이 아니라 layout 분리와 stroke 합성 가능성을 검증하기 위한 실험 코드입니다.
