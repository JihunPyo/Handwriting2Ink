# Handwriting2Ink 인수인계 문서

이 문서는 다음 작업자가 현재 코드베이스를 빠르게 이어받을 수 있도록 정리한 인수인계 문서입니다. 자세한 실험 이력은 `commit_log.md`, 실행 예시는 `README.md`에 따로 정리되어 있으니 함께 확인하면 됩니다.

## Chapter 1. 프로젝트의 목적과 현재 결론

### 1.1 프로젝트 목적

Handwriting2Ink는 손글씨나 손그림이 들어 있는 문서 이미지를 입력으로 받아, 이미지 속 필기와 도형을 stroke 좌표열로 변환해 다시 그려 보는 실험 프로젝트입니다. 최종 목표는 종이에 사람이 쓴 흐름을 디지털 잉크처럼 재현하는 것입니다.

현재 코드는 두 흐름으로 나뉘어 있습니다. 하나는 이미지 전체를 바로 전처리하고 skeletonize해서 stroke를 추출하는 기본 파이프라인입니다. 다른 하나는 OCR로 text/shape 영역을 먼저 crop한 뒤, crop별 stroke를 원래 위치로 다시 배치하는 OCR 파일럿 파이프라인입니다.

### 1.2 현재까지 확인한 핵심 결론

이 코드베이스의 핵심은 `skeletonizer.py`와 `stroke_extractor.py`입니다. `skeletonizer.py`는 이미지를 binary와 skeleton으로 만들고, `stroke_extractor.py`는 skeleton graph를 stroke 좌표열로 변환합니다.

`ocr_layout.py`는 전체 파이프라인의 통합 진입점이 아닙니다. 이 파일은 OCR로 text/shape crop과 `regions.json`을 만드는 선행 단계입니다. OCR crop을 실제 stroke로 바꾸고 원본 위치에 합성하는 작업은 `render_strokes.py`가 맡고 있습니다. 따라서 현재 OCR 기반 실험은 하나의 완성된 통합 파이프라인이라기보다, `ocr_layout.py` 실행 후 `render_strokes.py`를 실행하는 2단계 구조로 이해하는 것이 맞습니다.

### 1.3 앞으로 가져가야 할 판단

OCR crop은 레이아웃을 분리하는 데 도움이 됩니다. 특히 큰 배경, 문서 외곽, 불필요한 주변 정보가 skeletonize로 들어가는 문제를 줄일 수 있습니다. 다만 stroke 품질 문제를 OCR만으로 해결할 수는 없습니다. 결과가 사람 눈에 잘 읽히지 않는 주된 이유는 skeletonize 과정에서 글자의 두께와 면적 정보가 1px 중심선으로 줄어들고, 이후 `stroke_extractor.py`가 branch point 기준으로 글자를 여러 segment로 쪼개기 때문입니다.

다음 리팩토링에서는 OCR 자체를 더 붙이는 것보다, 전처리, 레이아웃 분리, skeletonize, stroke 추출, 렌더링을 명확한 단계로 나누는 것이 우선입니다. 각 단계의 입력과 출력이 분명해지면 이후 품질 개선도 훨씬 안전하게 진행할 수 있습니다.

## Chapter 2. 현재 파이프라인 구조

### 2.1 기본 stroke 파이프라인

기본 파이프라인의 진입점은 `simulate_drawing.py`입니다. 이 파일은 입력 이미지를 받아 `skeletonizer.load_and_preprocess()`로 gray와 binary를 만들고, `skeletonizer.skeletonize_zhang()`으로 skeleton을 만든 다음, `stroke_extractor.extract_strokes()`로 stroke 좌표열을 얻습니다. 마지막으로 결과 이미지를 저장하거나 Turtle 애니메이션을 실행합니다.

흐름은 다음과 같습니다.

```text
image
  -> load_and_preprocess
  -> skeletonize_zhang
  -> extract_strokes
  -> save_result_image / save_black_strokes_image / turtle
```

이 경로는 단순하고 디버깅하기 쉽습니다. 대신 이미지 전체가 바로 전처리 대상이기 때문에 배경, 표, 도형, 종이 외곽선, 잡음까지 skeletonize될 수 있습니다. 문서 사진처럼 배경 정보가 많은 입력에서는 이 한계가 바로 드러납니다.

### 2.2 OCR crop 기반 파일럿 파이프라인

OCR 파일럿은 두 단계로 봐야 합니다.

첫 번째 단계는 `ocr_layout.py`입니다. PaddleOCR mobile 모델로 text polygon과 bbox를 찾고, 가까운 text box를 묶어 `ocr_merged` region을 만듭니다. 동시에 foreground mask에서 text mask를 제외해 shape 후보도 분리합니다. 이 단계에서 중요한 산출물은 `regions.json`, `crops/text_*.png`, `crops/shape_*.png`입니다.

두 번째 단계는 `render_strokes.py`입니다. 이 파일은 `regions.json`에서 `ocr_merged` text bbox를 읽고, 각 `text_*.png` crop을 따로 전처리, skeletonize, stroke 추출합니다. 이후 crop-local stroke 좌표에 bbox의 `(x, y)` offset을 더해 원본 이미지 좌표계로 되돌립니다. 즉 crop 이미지들을 먼저 한 장으로 붙인 뒤 처리하는 방식이 아니라, crop별로 stroke를 만든 다음 좌표만 합성하는 방식입니다.

```text
ocr_layout.py
  image
    -> OCR text boxes
    -> merged text regions
    -> text/shape masks
    -> regions.json + crops

render_strokes.py
  regions.json + crops/text_*.png
    -> crop별 preprocess/skeleton/stroke
    -> bbox offset 적용
    -> 하나의 stroke set으로 합성
```

### 2.3 디버그 경로를 해석하는 방법

`render_strokes.py`에는 `--save_crop_debug`, `--save_merged_debug`, `--save_stroke_data` 옵션이 있습니다.

`--save_crop_debug`는 실제로 사용하는 per-crop 처리 경로를 확인하기 위한 옵션입니다. crop별 scaled crop, binary, skeleton, overlay를 저장하므로 품질 문제를 볼 때 가장 먼저 확인해야 합니다.

`--save_merged_debug`는 비교용입니다. crop 이미지를 원래 위치에 붙인 canvas를 다시 전처리하는 방식인데, 이 경우 crop 내부의 회색 배경이 전경으로 잡히는 문제가 생길 수 있습니다. 이 경로는 production 후보라기보다, “왜 crop을 먼저 이미지로 병합한 뒤 전역 전처리하는 방식이 위험한지” 확인하기 위한 디버그로 보면 됩니다.

## Chapter 3. 파일별 역할과 주의점

### 3.1 코어 파일

`skeletonizer.py`는 전처리와 Zhang-Suen skeletonize를 담당합니다. 현재 전처리는 gray 변환, Gaussian blur, Otsu inverse threshold, morphology close/open 정도로 단순합니다. 여러 CLI가 이 파일을 공통으로 쓰기 때문에, 여기서 동작을 바꾸면 기본 파이프라인과 OCR crop 파이프라인 모두에 영향을 줍니다.

`stroke_extractor.py`는 이 프로젝트에서 가장 중요한 알고리즘 파일입니다. skeleton 픽셀을 graph로 만들고, endpoint와 branch point를 찾고, branch point를 제거해 segment를 나눈 뒤, 방향 연속성 기준으로 segment를 다시 병합합니다. 현재 글자가 잘게 쪼개지거나 읽기 어렵게 보이는 문제는 대부분 이 파일의 graph 해석과 skeleton 정보 손실 사이에서 발생합니다. 리팩토링할 때는 한 번에 크게 고치기보다 graph 생성, segment 분리, merge scoring, stroke ordering을 단계별로 나누는 편이 안전합니다.

### 3.2 실행 파일

`simulate_drawing.py`는 기본 파이프라인 실행과 결과 저장을 담당합니다. `render_strokes.py`도 이 파일의 저장 함수를 재사용합니다. 따라서 stroke 두께, 3패널 결과 이미지, 흑백 결과 이미지 관련 변경은 두 파이프라인에 함께 영향을 줄 수 있습니다.

`skeletonizer_visualize.py`는 skeletonizer 품질을 확인하는 보조 CLI입니다. stroke 추출을 보기 전에 binary와 skeleton이 제대로 나오는지 확인하는 용도입니다. 전처리를 바꾸기 전후에는 이 파일로 먼저 결과를 비교하는 것이 좋습니다.

### 3.3 OCR 파일럿 파일

`ocr_layout.py`는 PaddleOCR에 의존하는 OCR layout 분리 파일럿입니다. 현재 OCR 엔진은 `PP-OCRv5_mobile_det`와 `korean_PP-OCRv5_mobile_rec`를 사용합니다. 이 프로젝트에서는 인식된 문자열보다 bbox와 polygon 좌표가 더 중요합니다. 현재 단계에서는 별도 학습 없이 사전학습 모델과 OpenCV 후처리만 사용하고 있습니다.

`render_strokes.py`는 현재 실험 옵션이 가장 많이 붙어 있는 파일입니다. crop upscaling, stroke 두께, crop debug, merged debug, stroke JSON export를 모두 담당합니다. 책임이 많이 커진 상태이므로 다음 리팩토링에서는 OCR 결과 로딩, crop 전처리, stroke 변환, 렌더링, JSON export를 분리하는 것이 좋습니다.

## Chapter 4. 실행과 운영 방법

### 4.1 기본 실행

Python 실행은 conda `DV` 환경을 기준으로 합니다.

```bash
conda run -n DV python simulate_drawing.py \
  --input images/inputs/test_heojw.jpeg \
  --save \
  --no_turtle
```

OCR 파일럿은 아래 순서로 실행합니다.

```bash
conda run -n DV python ocr_layout.py \
  --input images/inputs/H2I_flowchart.jpeg \
  --save_crops \
  --debug
```

```bash
conda run -n DV python render_strokes.py \
  --pilot_dir pilot_outputs/H2I_flowchart \
  --crop_scale 2.0 \
  --black_thickness 2 \
  --save_crop_debug \
  --save_stroke_data
```

### 4.2 Git과 산출물 관리

현재 `main`은 GitHub 원격 `origin/main`과 동기화되어 있습니다. 이미지 입력, 결과 이미지, OCR 출력, Paddle cache는 Git에 올리지 않는 정책입니다. `.gitignore`는 `*.png`, `*.jpg`, `*.jpeg`, `pilot_outputs/`, `.paddlex_cache/`, `.mplconfig/`, `.xdg_cache/`를 무시합니다.

Markdown도 기본적으로 무시하지만 `README.md`, `commit_log.md`, `HANDOFF.md`는 추적 대상입니다. 실험 변경은 `commit_log.md`에 누적하고, 외부 공유용 설명은 `README.md`, 후임자용 맥락은 `HANDOFF.md`에 정리하는 방식으로 유지하면 됩니다.

### 4.3 다음 리팩토링 권장 방향

가장 먼저 상위 orchestration 계층을 만드는 것을 권장합니다. 예를 들어 `pipeline.py`나 `run_ocr_stroke_pipeline.py`가 `ocr_layout.py`와 `render_strokes.py`의 흐름을 하나로 묶으면, 현재의 2단계 실행 구조가 훨씬 명확해집니다.

그 다음은 `render_strokes.py`를 분리하는 작업입니다. 지금 이 파일은 CLI, region 로딩, crop preprocessing, stroke extraction, rendering, debug export, JSON export를 모두 담당합니다. 리팩토링 초기에는 기능을 바꾸지 말고 함수와 책임만 분리하는 방식이 안전합니다.

마지막으로 stroke 품질 개선은 별도 작업으로 분리하는 것이 좋습니다. 품질 개선은 단순 리팩토링이 아니라 알고리즘 변경입니다. 특히 `stroke_extractor.py`의 branch point 처리와 segment merge scoring을 바꿀 때는 crop별 binary/skeleton debug 이미지를 먼저 저장하고, 같은 입력에 대해 변경 전후를 비교해야 합니다.
