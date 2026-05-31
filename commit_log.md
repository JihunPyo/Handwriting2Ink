# Commit Log

## 2026-06-01 GoodNotes GUI 컨트롤러 smoke test 추가

- `mac_worker/goodnotes_controller.py`를 추가했다.
  - GoodNotes 활성화, 전체화면 전환, 전면 앱 확인, 펜/검은색 버튼 좌표 클릭, 중앙 15px 가로선 입력을 하나의 smoke test 명령으로 분리했다.
  - `--execute`가 없으면 dry-run으로 화면 크기, 펜 좌표, 종이 영역, 선 중심점, 입력 방식을 출력하도록 했다.
  - `--pen_point`, `--black_color_point`, `--paper_rect`, `--line_center`, `--driver`, `--countdown` 옵션을 지원하도록 했다.
  - 실제 실행에서는 펜 버튼 좌표를 기본 필수값으로 두고, 입력 계층만 확인할 때만 `--skip_pen_select`로 펜 선택을 명시적으로 생략하도록 했다.
- `mac_worker/config.json`에 `goodnotes_controller` 설정 섹션을 추가했다.
  - GoodNotes 전체화면 UI에서 캘리브레이션한 펜 버튼 좌표, 검은색 버튼 좌표, 종이 영역 좌표를 저장할 수 있게 했다.
  - 실제 GoodNotes 입력 확인 결과를 반영해 GUI 컨트롤러 기본 입력 방식을 `drag`로 설정했다.
- `mac_worker/README.md`에 GoodNotes GUI 컨트롤러 smoke test 실행 절차를 추가했다.
- GoodNotes 단축키 정보를 컨트롤러에 반영했다.
  - `cmd+p`로 펜 선택, `cmd+l`로 올가미 선택을 수행하는 hotkey 모드를 추가했다.
  - 버튼 좌표 클릭 대신 hotkey 모드를 기본 도구 선택 방식으로 설정했다.
  - 테스트 선 입력 후 올가미 전환까지 확인할 수 있는 `--select_lasso_after_draw` 옵션을 추가했다.
- `strokes.json` replay 경로에도 펜 선택 단축키를 연결했다.
  - `goodnotes_writer.py`에 `--pen_hotkey` 옵션을 추가해 실제 stroke 입력 직전에 `cmd+p`를 보낼 수 있게 했다.
  - `mac_worker/worker.py`가 replay 모드에서 `pen_hotkey` 설정을 `goodnotes_writer.py`에 전달하도록 했다.
  - `mac_worker/config.json`에 replay용 `pen_hotkey` 기본값을 `cmd+p`로 추가했다.
- `goodnotes_controller.py`에 `strokes.json` replay 모드를 추가했다.
  - GoodNotes 전면화, 전체화면 전환, `cmd+p` 펜 선택 후 중앙 테스트 선 대신 실제 `strokes.json`을 그릴 수 있게 했다.
  - `--strokes`, `--target_rect`, `--fit`, `--sample_step`, `--point_delay`, `--stroke_delay` 옵션을 추가했다.
  - `goodnotes_writer.py`의 stroke 로딩, 좌표 매핑, 샘플링, replay 함수를 재사용하도록 했다.

## 2026-06-01 순차 확인 절차 보강

- `scripts/e2e_smoke_test.py`를 추가했다.
  - FastAPI `TestClient`로 health, 이미지 업로드, mock `strokes.json` 생성, worker claim, strokes 다운로드, worker 상태 보고, binary 업로드, iPad binary 다운로드, delivered 보고 순서를 검증하도록 했다.
  - 실제 서버 프로세스나 GoodNotes 실행 없이 HTTP 계약과 job 상태 전이를 먼저 확인할 수 있게 했다.
- `E2E_SKELETON.md`와 `server/README.md`를 수정했다.
  - 실제 코드에서 사용하는 `H2I_STROKE_MODE=pipeline` 환경 변수명으로 문서를 정정했다.
  - `mac_worker/config.json`의 현재 설정 구조와 smoke test 실행 절차를 문서에 반영했다.
- 실제 pipeline 연결 확인을 진행했다.
  - PaddleOCR 모델 캐시를 프로젝트 내부 `.paddlex_cache/`에 생성해 `pipeline.py` 직접 실행을 통과시켰다.
  - `H2I_STROKE_MODE=pipeline` 서버에서 이미지 업로드 후 실제 `crop_stroke_composite_strokes.json`이 생성되는 것을 확인했다.
  - 서버가 `layout_overlay.png`, `crop_stroke_composite_black.png`, `crop_stroke_composite_summary.json`, `run_meta.json`을 job 루트에도 복사하도록 보강했다.
  - 로컬 OCR/Matplotlib 캐시 디렉토리를 `.gitignore`에 추가했다.
- GoodNotes 자동화 안정화 준비를 시작했다.
  - `mac_worker/preflight.py`를 추가해 `target_rect`, pasteboard type, `pyautogui`, GoodNotes 앱 설치/실행 상태, Swift pasteboard dump script, `strokes.json`을 점검할 수 있게 했다.
  - `mac_worker/worker.py`가 replay 모드에서 `sample_step`, `point_delay`, `stroke_delay`, `countdown` 설정을 `goodnotes_writer.py`에 전달하도록 수정했다.
  - Swift pasteboard dump 실행 시 `CLANG_MODULE_CACHE_PATH`를 `/private/tmp` 아래로 지정해 홈 디렉토리 캐시 권한 문제를 피하도록 했다.
  - `mac_worker/config.json`과 `mac_worker/README.md`에 실제 replay 안정화 설정과 preflight 절차를 반영했다.
  - `--require-display` 옵션을 추가해 실제 마우스 입력 전 `pyautogui`가 유효한 화면 크기를 읽는지 필수 조건으로 검사할 수 있게 했다.
  - GoodNotes 실입력 smoke test용 `mac_worker/samples/single_stroke.json`을 추가하고, 실제 입력 전 사용할 최소 검증 명령을 문서화했다.
  - `--require-frontmost-goodnotes` 옵션을 추가해 실제 입력 전에 GoodNotes가 전면 앱인지 확인할 수 있게 했고, 전면 앱 확인에 timeout을 적용했다.
  - sandbox 밖 preflight에서 `pyautogui` 화면 크기 `1920x1080`, GoodNotes 실행 상태, GoodNotes 전면 앱 상태를 확인했다.
  - `goodnotes_writer.py --execute`로 최소 단일 stroke 입력 명령이 오류 없이 완료되는 것을 확인했다.
  - 사용자의 눈 검증에서 실제 획이 보이지 않아, `goodnotes_writer.py`가 매핑된 화면 좌표 범위와 시작/끝 좌표를 출력하도록 보강했다.
  - 실제 입력 직전 GoodNotes 전면 앱을 확인하는 `--require_frontmost_goodnotes` 옵션을 추가하고 워커 replay 설정에 연결했다.
  - 좌표 변환 문제와 입력 권한/도구 문제를 분리하기 위해 절대 화면 좌표 선 입력 도구 `mac_worker/calibrate_input.py`를 추가했다.
  - `--activate_goodnotes` 옵션을 추가해 실제 입력 전에 GoodNotes 앱을 전면으로 올리도록 했다.
  - 워커 replay 설정에 `activate_goodnotes`를 연결하고, 절대좌표 캘리브레이션 도구에도 동일한 GoodNotes 활성화 옵션을 추가했다.

## 2026-05-31 E2E 연결 골격 구현

- FastAPI 서버 골격을 추가했다.
  - `POST /api/jobs` 이미지 업로드 및 job 생성 API를 구현했다.
  - 기본 `mock` 모드에서 `crop_stroke_composite_strokes.json`을 생성하도록 했다.
  - `GET /api/jobs/{job_id}` 상태 조회와 `GET /api/jobs/{job_id}/binary` 다운로드 API를 구현했다.
  - Mac 워커용 job claim, strokes 다운로드, 상태 보고, binary 업로드, 실패 보고 API를 구현했다.
- Mac GUI 워커 골격을 추가했다.
  - 서버 polling, `strokes.json` 다운로드, 목 GoodNotes binary 생성, 서버 업로드 흐름을 구현했다.
  - `replay` 모드에서 기존 `goodnotes_writer.py`와 Swift pasteboard dump script를 호출할 수 있는 경계를 마련했다.
- iPad SwiftUI 앱 소스 골격을 추가했다.
  - 이미지 선택, 서버 업로드, job polling, binary 다운로드, `UIPasteboard` 기록 흐름을 구현했다.
  - 기존 `GoodNotesRestoreApp/GoodNotesRestoreApp/` 앱 소스를 기준으로 서버 URL 입력과 API endpoint 생성을 정리했다.
- 검증 결과를 기록했다.
  - `conda run -n DV python -m compileall server mac_worker` 문법 검증을 통과했다.
  - FastAPI `TestClient`로 업로드부터 binary 다운로드까지 목 E2E API 흐름을 확인했다.
- 로컬 런타임 산출물을 제외하기 위해 `.gitignore`를 추가했다.
