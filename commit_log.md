# Commit Log

## 2026-06-01 순차 확인 절차 보강

- `scripts/e2e_smoke_test.py`를 추가했다.
  - FastAPI `TestClient`로 health, 이미지 업로드, mock `strokes.json` 생성, worker claim, strokes 다운로드, worker 상태 보고, binary 업로드, iPad binary 다운로드, delivered 보고 순서를 검증하도록 했다.
  - 실제 서버 프로세스나 GoodNotes 실행 없이 HTTP 계약과 job 상태 전이를 먼저 확인할 수 있게 했다.
- `E2E_SKELETON.md`와 `server/README.md`를 수정했다.
  - 실제 코드에서 사용하는 `H2I_STROKE_MODE=pipeline` 환경 변수명으로 문서를 정정했다.
  - `mac_worker/config.json`의 현재 설정 구조와 smoke test 실행 절차를 문서에 반영했다.

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
