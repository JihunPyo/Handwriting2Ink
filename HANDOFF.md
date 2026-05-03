# Handwriting2Ink 인수인계 문서

이 문서는 후임자가 현재 코드베이스의 맥락을 빠르게 이어받기 위한 문서입니다. 세부 실험 로그는 `commit_log.md`, 사용자-facing 실행 요약은 `README.md`를 함께 보면 됩니다.

## Chapter 1. 프로젝트의 목적과 현재 결론

### 1.1 프로젝트 목적

Handwriting2Ink는 손글씨 또는 손그림 문서 이미지를 입력으로 받아, 이미지 안의 필기/도형을 stroke 좌표열로 바꿔 다시 그려 보는 실험 프로젝트입니다. 최종적으로는 사람이 종이에 그린 흐름을 디지털 잉크처럼 재현하는 것이 목표입니다.

현재 코드베이스는 크게 두 축으로 나뉩니다. 첫 번째는 이미지 전체를 바로 skeletonize해서 stroke를 추출하는 기본 파이프라인이고, 두 번째는 OCR로 text/shape 영역을 먼저 crop한 뒤 crop별 stroke를 원래 위치로 합성하는 파일럿 파이프라인입니다.

### 1.2 현재까지의 핵심 결론

현재 프로젝트의 핵심 알고리즘은 `skeletonizer.py`와 `stroke_extractor.py`입니다. `skeletonizer.py`는 이미지를 binary/skeleton으로 만들고, `stroke_extractor.py`는 skeleton graph를 stroke 좌표열로 바꿉니다.

`pilot_ocr_layout.py`는 전체 통합 엔트리포인트가 아닙니다. 이 파일은 OCR로 text/shape crop과 `regions.json`을 만드는 선행 단계입니다. OCR crop을 실제 stroke로 바꾸고 원래 위치에 합성하는 작업은 `render_pilot_strokes.py`가 담당합니다. 따라서 현재 전체 OCR 실험은 단일 파이프라인 파일 하나로 통합된 상태가 아니라, `pilot_ocr_layout.py` 실행 후 `render_pilot_strokes.py`를 실행하는 2단계 구조입니다.

### 1.3 지금 상태에서 가장 중요한 기술적 판단

OCR crop은 레이아웃 분리에 어느 정도 도움이 됩니다. 큰 배경이나 문서 외부 정보가 skeletonize로 들어오는 문제를 줄일 수 있습니다. 하지만 stroke 품질 문제는 OCR만으로 해결되지 않습니다. 사람이 읽기 어려운 결과가 나오는 주된 이유는 skeletonize가 글자의 면적과 두께 정보를 1px 중심선으로 줄이고, `stroke_extractor.py`가 branch point 기준으로 글자를 여러 segment로 쪼개기 때문입니다.

따라서 다음 리팩토링의 핵심은 OCR 자체가 아니라, “전처리/레이아웃 분리/스켈레톤/stroke 추출/렌더링”을 명확히 분리하고, 각 단계의 입력과 출력을 명시하는 것입니다.

## Chapter 2. 현재 파이프라인 구조

### 2.1 기본 stroke 파이프라인

기본 파이프라인의 진입점은 `simulate_drawing.py`입니다. 입력 이미지를 받아 `skeletonizer.load_and_preprocess()`로 gray/binary를 만들고, `skeletonizer.skeletonize_zhang()`으로 skeleton을 만든 뒤, `stroke_extractor.extract_strokes()`로 stroke 좌표열을 얻습니다. 이후 `save_result_image()`와 `save_black_strokes_image()`로 결과를 저장하거나 Turtle 애니메이션을 실행합니다.

흐름은 다음과 같습니다.

```text
image
  -> load_and_preprocess
  -> skeletonize_zhang
  -> extract_strokes
  -> save_result_image / save_black_strokes_image / turtle
```

이 경로는 코드가 단순하고 디버깅하기 쉽지만, 이미지 전체가 바로 전처리 대상이므로 배경, 표, 도형, 종이 외곽선, 잡음이 같이 skeletonize될 수 있습니다.

### 2.2 OCR crop 기반 파일럿 파이프라인

OCR 파일럿은 두 단계입니다.

첫 번째 단계는 `pilot_ocr_layout.py`입니다. PaddleOCR mobile 모델로 text polygon과 bbox를 검출하고, 가까운 text box를 병합해 `ocr_merged` region을 만듭니다. 동시에 foreground mask에서 text mask를 제외해 shape 후보도 분리합니다. 이 단계의 핵심 산출물은 `regions.json`과 `crops/text_*.png`, `crops/shape_*.png`입니다.

두 번째 단계는 `render_pilot_strokes.py`입니다. `regions.json`에서 `ocr_merged` text bbox를 읽고, 각 `text_*.png` crop을 개별적으로 전처리/skeletonize/stroke 추출합니다. 그 다음 crop-local stroke 좌표에 bbox의 `(x, y)` offset을 더해서 원본 이미지 좌표계로 되돌립니다. 즉 crop 이미지를 먼저 한 장으로 붙인 뒤 전처리하는 방식이 아니라, crop별로 stroke를 만든 뒤 좌표만 합성하는 방식입니다.

```text
pilot_ocr_layout.py
  image
    -> OCR text boxes
    -> merged text regions
    -> text/shape masks
    -> regions.json + crops

render_pilot_strokes.py
  regions.json + crops/text_*.png
    -> crop별 preprocess/skeleton/stroke
    -> bbox offset 적용
    -> 하나의 stroke set으로 합성
```

### 2.3 디버그 경로의 의미

`render_pilot_strokes.py`에는 `--save_crop_debug`, `--save_merged_debug`, `--save_stroke_data` 옵션이 있습니다. `--save_crop_debug`는 실제 per-crop 경로의 중간 결과를 보기 위한 것이므로 중요합니다. scaled crop, binary, skeleton, overlay를 crop별로 저장합니다.

반면 `--save_merged_debug`는 비교용입니다. crop 이미지를 원래 위치에 붙인 canvas를 다시 전처리하면 crop 내부의 회색 배경이 전경으로 잡히는 문제가 생길 수 있습니다. 이 경로는 production 후보라기보다 “왜 병합 후 전역 전처리가 위험한지”를 확인하기 위한 디버그입니다.

## Chapter 3. 파일별 역할과 주의점

### 3.1 코어 파일

`skeletonizer.py`는 전처리와 Zhang-Suen skeletonize만 담당합니다. 현재 전처리는 gray 변환, Gaussian blur, Otsu inverse threshold, morphology close/open 정도로 단순합니다. 이 파일은 여러 CLI에서 공통으로 쓰이므로, 변경하면 기본 파이프라인과 OCR crop 파이프라인에 동시에 영향을 줍니다.

`stroke_extractor.py`는 프로젝트의 핵심 난이도가 모여 있는 파일입니다. skeleton 픽셀을 graph로 만들고, endpoint/branch point를 찾고, branch point를 제거해 segment를 분리한 뒤, 방향 연속성 기준으로 segment를 병합합니다. 현재 결과물이 글자처럼 잘 안 보이는 문제는 대부분 이 파일의 graph 해석과 skeleton 정보 손실 사이에서 발생합니다. 리팩토링할 때는 이 파일을 한 번에 크게 바꾸기보다, graph 생성, segment 분리, merge scoring, stroke ordering을 모듈 단위로 나누는 것이 안전합니다.

### 3.2 실행 파일

`simulate_drawing.py`는 기본 파이프라인 실행과 결과 저장을 담당합니다. `render_pilot_strokes.py`도 이 파일의 저장 함수를 재사용합니다. 따라서 저장 이미지의 stroke 두께, 3패널 출력, 흑백 출력 관련 변경은 두 파이프라인 모두에 영향을 줄 수 있습니다.

`skeletonizer_visualize.py`는 skeletonizer 품질을 확인하는 보조 CLI입니다. stroke 추출 전에 binary/skeleton 단계가 잘 됐는지 보는 용도입니다. 전처리 변경을 시작하기 전후로 이 파일을 먼저 돌려보는 것이 좋습니다.

### 3.3 OCR 파일럿 파일

`pilot_ocr_layout.py`는 PaddleOCR에 강하게 의존합니다. OCR 엔진은 `PP-OCRv5_mobile_det`와 `korean_PP-OCRv5_mobile_rec`를 사용합니다. 인식 문자열보다는 bbox와 polygon 좌표가 중요합니다. 현재 v1에서는 별도 학습을 하지 않고 사전학습 모델과 OpenCV 후처리만 사용합니다.

`render_pilot_strokes.py`는 현재 가장 많은 실험 옵션이 붙어 있는 파일입니다. crop upscaling, stroke 두께, crop debug, merged debug, stroke JSON export를 모두 담당합니다. 기능이 늘면서 책임이 커졌으므로, 다음 리팩토링에서는 OCR 결과 로딩, crop 전처리, stroke 변환, 렌더링, JSON export를 분리하는 것이 좋습니다.

## Chapter 4. 실행과 운영 방법

### 4.1 기본 실행

Python 실행은 conda `DV` 환경을 기준으로 합니다.

```bash
conda run -n DV python simulate_drawing.py \
  --input images/inputs/test_heojw.jpeg \
  --save \
  --no_turtle
```

OCR 파일럿은 다음 순서로 실행합니다.

```bash
conda run -n DV python pilot_ocr_layout.py \
  --input images/inputs/H2I_flowchart.jpeg \
  --save_crops \
  --debug
```

```bash
conda run -n DV python render_pilot_strokes.py \
  --pilot_dir pilot_outputs/H2I_flowchart \
  --crop_scale 2.0 \
  --black_thickness 2 \
  --save_crop_debug \
  --save_stroke_data
```

### 4.2 Git과 산출물 관리

현재 `main`은 GitHub 원격 `origin/main`과 동기화되어 있습니다. 이미지 입력, 결과 이미지, OCR 출력, Paddle cache는 Git에 올리지 않는 정책입니다. `.gitignore`는 `*.png`, `*.jpg`, `*.jpeg`, `pilot_outputs/`, `.paddlex_cache/`, `.mplconfig/`, `.xdg_cache/`를 무시합니다.

Markdown도 기본적으로 무시하지만 `README.md`, `commit_log.md`, 그리고 이 문서 `HANDOFF.md`는 추적 대상입니다. 실험 내용을 남길 때는 `commit_log.md`에 누적 기록하고, 외부 공유용 설명은 `README.md` 또는 `HANDOFF.md`에 정리하는 방식이 좋습니다.

### 4.3 다음 리팩토링 권장 방향

가장 먼저 만들면 좋은 것은 상위 orchestration 계층입니다. 예를 들어 `pipeline.py` 또는 `run_ocr_stroke_pipeline.py`가 `pilot_ocr_layout.py`와 `render_pilot_strokes.py`의 흐름을 하나로 묶으면 후임자가 실행 흐름을 훨씬 쉽게 이해할 수 있습니다.

그 다음은 `render_pilot_strokes.py`의 분리입니다. 현재 이 파일은 CLI, region 로딩, crop preprocessing, stroke extraction, rendering, debug export, JSON export를 모두 담당합니다. 리팩토링할 때는 기능 변경 없이 함수 이동만 먼저 하는 것이 안전합니다.

마지막으로 stroke 품질 개선은 별도 작업으로 분리하는 것이 좋습니다. 품질 개선은 단순 리팩토링이 아니라 알고리즘 변경입니다. 특히 `stroke_extractor.py`의 branch point 처리와 segment merge scoring을 바꿀 때는 crop별 binary/skeleton debug 이미지를 먼저 저장하고, 변경 전후를 같은 입력으로 비교해야 합니다.
