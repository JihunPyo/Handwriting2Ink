# H2I End-to-End Skeleton

## 목적

본 문서는 `docs/development-plan.md`의 전체 구조를 먼저 연결하기 위한 개발용 뼈대를 설명한다.

현재 뼈대는 실제 GoodNotes 자동화를 완성하지 않는다. 대신 다음 연결 구조가 실제 HTTP 요청으로 이어진다는 점을 검증한다.

```text
iPad 앱
→ FastAPI 서버에 이미지 업로드
→ 서버가 strokes.json 생성
→ Mac 워커가 strokes.json 다운로드
→ Mac 워커가 GoodNotes 재생 단계를 호출
→ Mac 워커가 binary 업로드
→ iPad 앱이 binary 다운로드
→ UIPasteboard에 기록
```

## 추가된 구성

```text
backend/
  app/
    main.py
    api/jobs.py
    api/worker.py
    services/job_service.py
    services/storage_service.py
    services/stroke_service.py
  requirements.txt
  storage/jobs/

workers/
  macos/
    worker.py
    goodnotes_writer.py
    dump_goodnotes_clipboard.swift
    config.json

frontend/
  ipados/
    GoodNotesRestoreApp.xcodeproj/
    GoodNotesRestoreApp/
      GoodNotesRestoreApp.swift
      ContentView.swift
      APIClient.swift
      Models.swift
      PasteboardWriter.swift
```

## 서버 실행

Python 실행은 프로젝트 규칙에 따라 `conda`의 `DV` 환경에서 수행한다.

```bash
conda run -n DV python -m pip install -r backend/requirements.txt
conda run -n DV python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

기본값은 `mock` stroke pipeline이다. 따라서 PaddleOCR이나 실제 `pipeline.py`가 없어도 업로드된 이미지에서 개발용 `strokes.json`을 생성한다.

실제 파이프라인을 호출하려면 다음 환경 변수를 사용한다.

```bash
H2I_STROKE_MODE=pipeline \
conda run -n DV python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## 순차 확인

서버 프로세스를 띄우기 전 API 라우팅과 job 상태 전이를 먼저 확인하려면 다음 smoke test를 실행한다.

```bash
conda run -n DV python scripts/e2e_smoke_test.py
```

이 테스트는 임시 storage를 사용해 다음 순서를 확인한다.

```text
1. /health 확인
2. /api/jobs 이미지 업로드
3. mock strokes.json 생성 확인
4. Mac 워커 job claim 확인
5. strokes.json 다운로드 확인
6. worker 상태 보고 확인
7. GoodNotes binary 업로드 확인
8. iPad binary 다운로드 확인
9. delivered 상태 보고 확인
```

## 서버 API 빠른 확인

```bash
curl -F "file=@/path/to/input.png" http://127.0.0.1:8000/api/jobs
curl http://127.0.0.1:8000/api/jobs/<job_id>
```

업로드 후 파일은 다음 위치에 저장된다.

```text
backend/storage/jobs/<job_id>/
  input.<ext>
  job.json
  events.jsonl
  crop_stroke_composite_strokes.json
```

## Mac 워커 실행

서버가 실행 중인 상태에서 다음 명령을 실행한다.

```bash
conda run -n DV python workers/macos/worker.py --once
```

기본 설정은 `workers/macos/config.json`에 있다.

```json
{
  "server_url": "http://127.0.0.1:8000",
  "worker_token": "dev-worker-token",
  "worker_id": "mac-worker-dev",
  "poll_interval_seconds": 3,
  "mode": "mock",
  "jobs_dir": "workers/macos/jobs",
  "target_rect": "320,180,980,720",
  "fit": "contain",
  "driver": "drag",
  "execute_goodnotes_writer": false,
  "pasteboard_type": "com.goodnotesapp.goodnotes5.notes"
}
```

현재 Mac 워커는 다음 순서로 동작한다.

```text
GET /api/worker/jobs/next
→ GET /api/worker/jobs/{job_id}/strokes
→ mock 모드에서는 개발용 goodnotes_clipboard_item0.bin 생성
→ POST /api/worker/jobs/{job_id}/binary
```

`mode`를 `replay`로 바꾸면 기존 `goodnotes_writer.py`를 호출한다. 실제 마우스 입력은 `execute_goodnotes_writer`가 `true`일 때만 수행된다.

## iPad 앱 연결

`frontend/ipados/GoodNotesRestoreApp` 아래 Swift 파일은 iPad 앱 target에 추가해서 사용할 수 있는 뼈대이다.

실제 iPad 기기에서는 `APIClient.swift`의 기본 URL을 Mac 또는 서버의 접근 가능한 주소로 바꿔야 한다.

```swift
APIClient(baseURL: URL(string: "http://<Mac IP>:8000")!)
```

iOS 시뮬레이터에서는 기본값인 `http://127.0.0.1:8000`을 사용할 수 있다.

## 다음 구현 단계

1. `mock_binary_upload` 대신 GoodNotes 올가미 복사 자동화와 `dump_goodnotes_clipboard.swift`를 연결한다.
2. 서버의 `mock` stroke pipeline을 `real` 모드로 바꾸고 기존 `pipeline.py` 실행을 안정화한다.
3. 파일 기반 job store를 PostgreSQL로 교체한다.
4. worker heartbeat와 timeout 실패 처리를 추가한다.
5. iPad 앱에 서버 URL 설정 화면과 실패 재시도 UI를 추가한다.
