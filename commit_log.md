# Commit Log

## 2026-04-13

### Branch
- `pilot-ocr-layout-python`

### Changes
- Added `pilot_ocr_layout.py` as an independent OCR layout pilot.
- Kept the existing handwriting extraction pipeline unchanged.
- Updated `.gitignore` to track `commit_log.md` and ignore OCR pilot outputs/cache directories.

### Dependency Notes
- Installed `paddlepaddle==3.2.0` in conda `DV`.
- Installed `paddleocr==3.2.0` in conda `DV`.
- Downgraded `numpy` in `DV` to `<2` to resolve PaddleX compatibility issues.
- Configured the pilot to use project-local cache directories:
  - `.paddlex_cache/`
  - `.mplconfig/`
  - `.xdg_cache/`

### Pilot Behavior
- OCR uses `PP-OCRv5_mobile_det` + `korean_PP-OCRv5_mobile_rec`.
- Raw OCR polygons are preserved.
- Merged text regions are grouped conservatively for crop generation.
- Shape regions are extracted from foreground minus text mask, then restricted by:
  - OCR-derived content ROI
  - bright document-region mask

### Test Results
- `test_heojw.jpeg`
  - raw text regions: `6`
  - merged text regions: `1`
  - shape regions: `0`
- `test_2.jpeg`
  - raw text regions: `19`
  - merged text regions: `7`
  - shape regions: `1`
- `H2I_flowchart.jpeg`
  - raw text regions: `24`
  - merged text regions: `8`
  - shape regions: `4`
- `H2I_flowchart_crop1.jpg`
  - raw text regions: `12`
  - merged text regions: `8`
  - shape regions: `5`

### Output Paths
- `pilot_outputs/test_heojw/`
- `pilot_outputs/test_2/`
- `pilot_outputs/H2I_flowchart/`
- `pilot_outputs/H2I_flowchart_crop1/`

## 2026-04-13

### Branch
- `pilot-ocr-layout-python`

### Local Asset Cleanup
- Organized root-level image files into dedicated directories to keep the project root cleaner.
- Created tracked placeholder files so the directory structure is preserved in Git.

### Directory Layout
- `images/inputs/`
  - original sample inputs and cropped source images
- `images/outputs/simulate/`
  - `_result.png`, `_strokes_black.png`, and related simulation outputs
- `images/outputs/skeleton/`
  - `_skeleton_overview.png` files
- `images/outputs/experiments/`
  - ad-hoc experimental result images such as shape-priority variants

### Notes
- Existing `pilot_outputs/` remains unchanged because it already groups OCR pilot outputs by input name.

## 2026-04-13

### Branch
- `pilot-crop-layout-render`

### Changes
- Removed the temporary crop-bitmap composition approach.
- Added a stroke-based pilot renderer for OCR crops.

### Purpose
- Convert each OCR text crop into strokes with the existing skeleton/stroke pipeline.
- Offset each crop's stroke coordinates by its original bbox position and render them on one canvas.

### Initial Verification
- `pilot_outputs/test_2/regions.json` contains `7` merged text regions.
- `pilot_outputs/test_2/crops/text_001.png` through `text_007.png` match the merged text bbox sizes, so text crop repositioning is feasible.

### Implementation
- Added `render_pilot_strokes.py`.
- Each `ocr_merged` text crop is processed independently with:
  - `load_and_preprocess`
  - `skeletonize_zhang`
  - `extract_strokes`
- Each crop-local stroke receives the crop bbox `(x, y)` offset and is merged into one global stroke list.
- Final rendering reuses `simulate_drawing.py` output functions.

### Test Output
- `pilot_outputs/test_2/crop_stroke_composite_result.png`
- `pilot_outputs/test_2/crop_stroke_composite_black.png`
- `pilot_outputs/test_2/crop_stroke_composite_summary.json`

### Test Result
- `test_2` produced `225` globally shifted strokes from `7` OCR text regions.
- The final rendered image preserves the relative layout of the original OCR crop regions.
