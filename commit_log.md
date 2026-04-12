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
