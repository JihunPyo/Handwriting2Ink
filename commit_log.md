# Commit Log

## 2026-09-01 Handwriting2Ink 앱 로고 v3 추가

- 흰색 바탕에 차콜과 저채도 세이지 두 가지 포인트 색상만 사용하는 로고로 단순화했다.
- 네 개의 이미지 픽셀이 하나의 굵은 필기선으로 이어지는 단일 심볼을 구성했다.
- 장식적인 그라데이션, 강한 그림자, 펜촉과 별도의 문서 외곽선을 배제해 작은 아이콘에서도 식별되도록 했다.
- 새 시안은 `docs/assets/handwriting2ink-app-icon-v3.png`에 저장하고 이전 시안은 비교용으로 보존했다.

## 2026-09-01 Handwriting2Ink 앱 로고 v2 추가

- 기존 시안의 강한 코발트·네온 대비와 미래적인 펜촉 형태를 제거했다.
- 따뜻한 종이 질감, 차콜 잉크, 저채도 세이지·블루그레이를 사용해 차분한 앱 아이콘으로 재설계했다.
- 최신 iPadOS 아이콘 가이드에 맞춰 중앙 중심의 단순한 실루엣, 충분한 안전 여백, 1024x1024 불투명 정사각형 원본을 유지했다.
- 새 시안은 `docs/assets/handwriting2ink-app-icon-v2.png`에 저장하고 기존 시안은 비교용으로 보존했다.

## 2026-09-01 Handwriting2Ink 앱 로고 추가

- 이미지의 픽셀 정보가 연속적인 잉크 stroke와 펜촉으로 변환되는 서비스 흐름을 앱 아이콘으로 시각화했다.
- `docs/assets/handwriting2ink-app-icon.png`에 iPadOS용 1024x1024 불투명 PNG 원본을 추가했다.
- 운영체제의 아이콘 마스크가 적용되도록 배경을 정사각형 전체에 채우고, 별도의 둥근 모서리나 투명 영역은 포함하지 않았다.

## 2026-09-01 Goodnotes 올가미 자동 전환 안정화

- 로컬 Goodnotes에서 검증된 펜 `cmd+p`, 올가미 `cmd+l` 단축키를 유지했다.
- 올가미 단축키 전송 직전에 Goodnotes를 다시 활성화하고 전면 앱 여부를 확인하도록 보강했다.
- 키 조합 전송 간격을 추가해 modifier와 문자 키가 너무 빠르게 전달되지 않도록 했다.
- `quartz_post_draw_delay=1.2`, `lasso_tool_delay=1.0`으로 stroke 커밋과 올가미 전환 대기 시간을 늘렸다.

## 2026-09-01 포트폴리오용 모노레포 구조 정리

- FastAPI 서버를 `backend/`, iPadOS 앱을 `frontend/ipados/`, Mac GUI 워커를 `workers/macos/`로 분리했다.
- OCR·스켈레톤·stroke 추출 코드를 `backend/pipeline/`으로 이동하고 서버 실행 경로와 import를 갱신했다.
- 개발 계획, E2E 문서, 조사 보고서를 `docs/`로 이동하고 향후 선별 이미지를 둘 `docs/assets/`를 마련했다.
- 테스트 확장을 위해 `tests/backend/`, `tests/pipeline/`, `tests/worker/` 경계를 마련했다.
- 기존 런타임 데이터와 로컬 설정이 새 경로에서도 추적되지 않도록 `.gitignore`를 갱신했다.
- 루트 포트폴리오 `README.md`는 별도 작업 대상으로 남겼다.

## 2026-09-01 로컬 분석 산출물 분리

- `scripts/poster_crop_effect_analysis.py`는 재현 가능한 분석 코드로 추적했다.
- `output/`, `outputs/`, 화면 녹화 파일은 로컬 생성물로 분류해 `.gitignore`에서 제외했다.
- 포트폴리오에 사용할 결과물은 추후 `docs/assets/`에 선별해서 추가하도록 분리했다.

## 2026-06-05 GoodNotes 올가미 backend 분리

- `mac_worker/goodnotes_controller.py`에 `lasso_input_backend` 설정을 추가했다.
  - stroke 입력은 `input_backend=quartz`를 유지하되, 올가미 입력은 기존에 성공한 `pyautogui` drag 경로를 기본으로 쓰도록 분리했다.
  - Swift `drag_path` 경로가 GoodNotes 올가미 선택 제스처를 다르게 해석할 수 있어, `lasso_driver=drag` 설정이 실제로 적용되는 PyAutoGUI 경로로 되돌렸다.
- `mac_worker/config.json`의 `goodnotes_controller.lasso_input_backend` 기본값을 `pyautogui`로 추가했다.
- `mac_worker/README.md`에 stroke backend와 lasso backend를 분리한 이유를 기록했다.

## 2026-06-05 Quartz stroke 재생 속도 하향 조정

- `mac_worker/config.json`과 `mac_worker/goodnotes_controller.py`의 `goodnotes_controller.quartz_stroke_velocity` 기본값을 `100.0`으로 통일했다.
  - GoodNotes가 Quartz drag 경로를 더 촘촘하게 샘플링할 수 있도록 stroke 재생 시간을 크게 늘리기 위한 조정이다.

## 2026-06-05 Swift Quartz replay 품질 안정화

- `mac_worker/goodnotes_quartz_replay.swift`의 Quartz 이벤트 입력을 보강했다.
  - `CGEventSource(.hidSystemState)`와 click state를 명시해 mouse event 성격을 더 안정적으로 전달하도록 했다.
  - button number, pressure, non-coalesced flag를 명시해 drag event가 GoodNotes에서 병합/누락되는 문제를 줄이도록 했다.
  - mouseDown 직후 짧은 대기를 추가해 GoodNotes가 stroke 시작을 놓치는 문제를 줄이도록 했다.
  - 원본 point를 그대로 빠르게 밀어 넣지 않고, stroke 경로 길이와 목표 속도에 맞춰 보간 좌표를 일정 간격으로 보내도록 했다.
- `mac_worker/goodnotes_controller.py`와 `mac_worker/config.json`의 Quartz 기본 속도를 조정했다.
  - `quartz_point_delay`를 `0.0015`, `quartz_stroke_delay`를 `0.008`로 조정했다.
  - `quartz_mouse_down_delay=0.006`을 추가했다.
  - 짧은 자소/문장부호 stroke가 무시되지 않도록 `quartz_min_stroke_duration=0.035`를 추가했다.
  - 길이 기반 replay용 `quartz_event_interval=0.004`, `quartz_stroke_velocity=650.0`을 추가했다.
  - stroke 입력 직후 올가미 전환 전 `quartz_post_draw_delay=0.8` 대기를 추가했다.
- `mac_worker/README.md`에 Quartz 이벤트가 너무 빠를 때 GoodNotes가 point를 병합/누락할 수 있다는 내용과 조정 방법을 기록했다.

## 2026-06-05 Swift Quartz replay CLI 추가

- `mac_worker/goodnotes_quartz_replay.swift`를 추가했다.
  - `CGEvent` 기반으로 stroke와 올가미 drag path를 입력하도록 했다.
  - JSON payload와 `--dry-run` 검증 모드를 지원하도록 했다.
  - SIGINT/SIGTERM 중단 시 마지막 좌표에서 mouseUp을 보내고 종료하도록 했다.
- `mac_worker/goodnotes_controller.py`에 `input_backend` 설정을 추가했다.
  - 기본값을 `quartz`로 두고, 기존 `pyautogui` stroke/올가미 replay 경로는 fallback으로 유지했다.
  - Swift 실행기는 `/private/tmp/h2i_goodnotes_quartz_replay`로 lazy compile하도록 했다.
  - Quartz 전용 `quartz_point_delay`, `quartz_stroke_delay` 설정을 추가했다.
- `mac_worker/config.json`과 `mac_worker/README.md`에 Quartz backend 기본값, fallback 방법, smoke test 절차를 반영했다.
- `mac_worker/preflight.py --check-swift`가 pasteboard dump와 Quartz replay Swift 파일을 함께 typecheck하도록 보강했다.

## 2026-06-01 Worker 기본 올가미 파라미터 조정

- 실제 GoodNotes 테스트에서 안정적으로 닫힌 올가미 파라미터를 `mac_worker/config.json` 기본값에 반영했다.
  - `lasso_padding`을 `40.0`으로 조정했다.
  - `lasso_drag_duration`을 `1.5`로 조정했다.
  - `lasso_point_count`를 `160`으로 조정했다.
  - `lasso_close_overlap`을 `48.0`으로 조정했다.
- `mac_worker/README.md`에 worker 기본 올가미 설정값을 기록했다.

## 2026-06-01 GoodNotes 올가미 닫힘 경로 안정화

- `mac_worker/goodnotes_controller.py`의 올가미 경로 생성을 보강했다.
  - 사각형 올가미가 마지막에 물방울 형태로 닫히는 문제를 줄이기 위해 시작점을 모서리가 아닌 위쪽 변 중앙으로 옮겼다.
  - 시작점으로 돌아온 뒤 바로 mouseUp하지 않고 `lasso_close_overlap`만큼 위쪽 변을 겹쳐 지나가도록 했다.
  - 5개 점짜리 사각형 대신 `lasso_point_count` 기반 중간점을 생성해 더 연속적인 올가미 경로를 입력하도록 했다.
  - 필요 시 `lasso_shape=ellipse`로 타원형 올가미를 테스트할 수 있게 했다.
- `mac_worker/config.json`과 `mac_worker/README.md`에 `lasso_shape`, `lasso_point_count`, `lasso_close_overlap` 설정을 추가했다.

## 2026-06-01 iPad job 상태 응답 계약 정렬

- `GoodNotesRestoreApp/GoodNotesRestoreApp/Models.swift`에서 계약에 없는 `strokes_ready` 필수 디코딩을 제거했다.
  - GitHub/Railway 서버의 `GET /api/jobs/{job_id}` 응답에 `strokes_ready`가 없어도 앱이 디코딩 실패하지 않도록 했다.
- `GoodNotesRestoreApp/GoodNotesRestoreApp/ContentView.swift`의 `strokes.json` 별도 표시 줄을 제거하고, 계약에 명시된 `status`와 `binary_ready` 중심으로 job 상태를 표시하도록 했다.

## 2026-06-01 로컬 워커 설정 분리

- `mac_worker/worker.py`가 `mac_worker/config.local.json`을 읽어 기본 config 위에 덮어쓰도록 했다.
  - 배포 worker token 같은 로컬 비밀값을 추적되는 `config.json`에 커밋하지 않기 위한 변경이다.
  - `H2I_SERVER_URL`, `H2I_WORKER_TOKEN` 환경 변수로도 서버 주소와 worker token을 덮어쓸 수 있게 했다.
- `.gitignore`에 `mac_worker/config.local.json`과 zip 산출물 제외 규칙을 추가했다.
- `mac_worker/config.json`의 `worker_token`은 개발용 기본값으로 되돌리고, 로컬 실행용 token은 ignored local config에 보관하도록 했다.

## 2026-06-01 iPad GoodNotesRestoreApp Xcode 프로젝트 추가

- `GoodNotesRestoreApp/GoodNotesRestoreApp.xcodeproj`를 추가해 기존 SwiftUI 소스를 Xcode에서 바로 열 수 있게 했다.
- `Info.plist`와 `Assets.xcassets`를 추가했다.
  - iPad 전용 target, 로컬 HTTP/LAN 서버 접근을 위한 ATS 및 local network 설명을 포함했다.
  - Xcode에서 바로 선택 가능한 shared scheme과 AccentColor asset을 포함했다.
- iPad 앱 흐름을 보강했다.
  - 기본 서버 URL을 Railway 배포 주소로 변경하고 `@AppStorage`로 저장하도록 했다.
  - 선택 이미지를 `UIImage`로 읽어 JPEG로 정규화한 뒤 FastAPI 서버에 업로드하도록 했다.
  - 업로드, job polling, binary 다운로드, `UIPasteboard` 기록, delivered 보고가 하나의 실행 버튼에서 이어지도록 했다.
  - binary가 이미 준비된 job에 대해 다시 다운로드/복사할 수 있는 재시도 버튼을 추가했다.
- `APIClientError`를 `LocalizedError`로 바꿔 서버 오류 메시지가 앱 화면에 읽히도록 했다.
- `GoodNotesRestoreApp/README.md`에 Xcode 프로젝트 실행 경로와 iPad 테스트 절차를 반영했다.

## 2026-06-01 GoodNotes stroke 중복 point 필터 추가

- `goodnotes_writer.py`에 `filter_strokes_by_distance()`와 `--min_point_distance` 옵션을 추가했다.
  - 화면 좌표 매핑 후 같은 좌표 또는 너무 가까운 point를 생략해 mouseDown 상태에서 같은 위치에 머무르는 입력을 줄이도록 했다.
  - GoodNotes가 중복 point 구간을 우클릭/롱프레스성 동작처럼 해석하는 문제를 줄이기 위한 변경이다.
- `mac_worker/goodnotes_controller.py`가 stroke replay 전에 `min_point_distance` 필터를 적용하도록 했다.
- `mac_worker/config.json`의 `goodnotes_controller.min_point_distance` 기본값을 `1.0`으로 추가했다.

## 2026-06-01 GoodNotes 자동 입력 전역 중단 키 추가

- `goodnotes_writer.py`에 전역 중단 플래그와 macOS Quartz 키 이벤트 리스너를 추가했다.
  - GoodNotes가 전면 앱이어도 `Esc` 또는 `Ctrl+C` 입력을 감지해 자동 입력을 중단할 수 있게 했다.
  - 터미널이 포커스를 잃어 일반 `KeyboardInterrupt`가 전달되지 않는 문제를 보완했다.
  - 입력 루프 내부에서 중단 플래그를 주기적으로 확인하고, 중단 시 마우스 버튼을 올린 뒤 종료하도록 했다.
- `mac_worker/goodnotes_controller.py`가 실제 실행 전에 전역 중단 리스너를 설치하도록 했다.
  - 올가미 드래그와 복사 재시도 중에도 중단 플래그를 확인하도록 했다.

## 2026-06-01 GoodNotes worker 기본 stroke 품질 설정 조정

- `mac_worker/config.json`의 `goodnotes_controller.sample_step`을 `10`에서 `1`로 변경했다.
  - worker 경로에서 10개 점마다 하나만 사용하는 sampling 때문에 곡선과 자소가 직선화되는 문제를 줄이기 위한 변경이다.
  - `point_delay`를 `0.002`, `stroke_delay`를 `0.02`로 조정해 전체 point를 사용하는 replay가 너무 빠르게 입력되지 않도록 했다.
- `mac_worker/README.md`에 `sample_step=10`은 위치 확인용이고, 실제 품질/worker 기본 실행은 `sample_step=1`을 사용해야 한다는 내용을 반영했다.

## 2026-06-01 GoodNotes 복사 단축키 안정화

- `pyautogui`의 macOS Command modifier 정식 키 이름이 `command`임을 반영했다.
  - `send_hotkey()`에서 `cmd` 입력을 `command`로 정규화하도록 했다.
  - `goodnotes_controller.py`의 기본 `copy_hotkey`를 `command+c`로 변경했다.
- 올가미 선택 확정 이후 복사 타이밍을 안정화했다.
  - `copy_delay`, `copy_retries`, `copy_retry_delay` 설정을 추가해 GoodNotes 선택 확정 후 복사 단축키를 보낼 수 있게 했다.
  - `mac_worker/config.json`에 기본 복사 대기/재시도 설정을 추가했다.

## 2026-06-01 올가미 smoke test용 단일 획 샘플 추가

- `mac_worker/samples/one_stroke_lasso_test.json`을 추가했다.
  - 기존 `single_stroke.json`보다 정사각형 비율에 가까운 한 획 폐곡선 샘플로 구성했다.
  - GoodNotes 중앙에 더 안정적으로 매핑해 펜 stroke와 올가미 선택을 함께 확인할 수 있게 했다.

## 2026-06-01 GoodNotes 펜 stroke 연속 입력 보강

- `goodnotes_writer.py`의 `driver=drag` 입력 방식을 수정했다.
  - 기존에는 각 point 구간마다 `pyautogui.dragTo()`가 독립 실행되어 mouseDown/mouseUp이 반복될 수 있었다.
  - 한 stroke 전체에서 mouseDown을 유지하고, 내부 point 이동은 `dragTo(..., mouseDownUp=False)`로 이어 보내도록 변경했다.
  - GoodNotes에서 획이 잘게 끊겨 들어가고 획 지우개/올가미 인식이 불안정해지는 문제를 줄이기 위한 변경이다.
- `mac_worker/README.md`에 연속 drag event 방식의 이유를 기록했다.

## 2026-06-01 GoodNotes 올가미 drag event 방식 보강

- `mac_worker/goodnotes_controller.py`의 올가미 드래그가 macOS drag event를 쓰도록 `lasso_driver` 설정을 추가했다.
  - 기존 올가미 드래그는 `mouseDown + moveTo + mouseUp` 방식이어서 GoodNotes에서 파란 올가미 파선이 나타나지 않을 수 있었다.
  - 기본값을 `drag`로 두고, 내부 이동에 `pyautogui.dragTo(..., mouseDownUp=False)`를 사용하도록 했다.
  - `cmd+l` 직후 도구 전환 안정화를 위해 `lasso_tool_delay` 설정을 추가했다.
- `mac_worker/config.json`과 `mac_worker/README.md`에 올가미 drag event 설정을 반영했다.

## 2026-06-01 배포 서버 워커 설정 반영

- `mac_worker/config.json`의 `server_url`을 Railway 배포 서버 주소로 변경했다.
- `worker_token`을 배포 서버용 워커 토큰으로 변경했다.

## 2026-06-01 Mac 워커 replay 경로를 GoodNotes 컨트롤러로 전환

- `mac_worker/worker.py`의 replay 경로를 `goodnotes_writer.py` 직접 호출에서 `mac_worker/goodnotes_controller.py --strokes` 호출로 변경했다.
  - 컨트롤러 config를 그대로 넘겨 `target_rect`, `sample_step`, `drag`, `cmd+p`, `cmd+l`, lasso padding, copy hotkey 설정을 한 곳에서 쓰도록 했다.
  - replay 모드에서는 기본적으로 `--copy_after_draw`를 붙여 stroke 입력 후 올가미 선택, bbox 드래그, `cmd+c`까지 수행하도록 했다.
  - 실제 실행 플래그는 새 `execute_goodnotes_controller`를 우선 사용하고, 기존 `execute_goodnotes_writer`도 호환용으로 인식하도록 했다.
  - `execute_goodnotes_controller=false` dry-run 상태에서는 이전 pasteboard가 업로드되지 않도록 binary 추출 전에 명시적으로 중단하도록 했다.
- `mac_worker/config.json`에 `execute_goodnotes_controller`와 `goodnotes_controller.copy_after_draw` 설정을 추가했다.
- `mac_worker/README.md`에 worker replay 호출 대상이 GoodNotes 컨트롤러로 바뀐 내용을 반영했다.

## 2026-06-01 GoodNotes 올가미 복사 자동화 추가

- `mac_worker/goodnotes_controller.py`에 `--copy_after_draw` 옵션을 추가했다.
  - `strokes.json`이 화면 좌표로 매핑된 뒤 stroke bbox를 계산하고, padding을 더한 올가미 선택 영역을 자동 산출하도록 했다.
  - stroke 입력 후 `cmd+l`, bbox 주변 사각형 드래그, `cmd+c` 순서로 GoodNotes 내용을 복사하도록 했다.
  - `--lasso_padding`, `--lasso_drag_duration`, `--copy_hotkey` 옵션을 추가했다.
- `mac_worker/config.json`에 올가미 복사 기본 설정을 추가했다.
- `mac_worker/README.md`에 `--copy_after_draw` 실행 예시와 padding 조정 방법을 추가했다.

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

## 2026-06-05 포스터용 OCR Crop 전처리 효과 분석

- `scripts/poster_crop_effect_analysis.py`를 추가했다.
  - 발표 문서의 원본 이미지와 pipeline 산출물을 기준으로 전체 이미지 직접 처리와 OCR crop 처리의 정량 지표를 계산하도록 했다.
  - 전경 픽셀, 스켈레톤 픽셀, 연결 성분, 끝점, 교차점, raw segment, 최종 stroke 수를 CSV와 마크다운으로 저장하도록 했다.
- `output/poster_crop_analysis/`에 포스터 결과 영역용 산출물을 생성했다.
  - `source_original.jpeg`에 발표 문서 원본 이미지를 저장했다.
  - `pipeline/`에 OCR layout, crop debug, stroke composite 결과를 생성했다.
  - `crop_effect_metrics.csv`, `crop_effect_metrics_by_crop.csv`, `crop_effect_analysis.md`를 생성했다.
  - `whole_direct_binary.png`, `whole_direct_skeleton.png`, `whole_direct_stroke_result.png`, `whole_direct_black.png`를 생성했다.
- 분석 결과를 기록했다.
  - 동일 해상도 기준 OCR crop 처리 영역은 전체 이미지 대비 36.2%로 계산되었다.
  - 전체 이미지 직접 처리 대비 OCR crop 처리에서 전경 픽셀은 84.2%, 스켈레톤 픽셀은 65.2%, raw segment 후보는 50.5% 감소했다.
  - 실제 pipeline crop_scale=2.0 기준으로는 최종 180개 stroke가 생성되었다.
- `output/poster_crop_analysis/ocr_crop_effect_metrics_table.pptx`를 생성했다.
  - 1장에는 포스터용 요약표와 감소율 카드 3개를 배치했다.
  - 2장에는 사용자가 제공한 raw metric table 전체 컬럼을 appendix 형식으로 정리했다.
  - artifact-tool 렌더 preview와 layout quality 검사를 수행했고, 최종 검사에서 error 0개를 확인했다.
