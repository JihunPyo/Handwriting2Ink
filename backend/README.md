# H2I FastAPI Server Skeleton

이 서버는 iPad 앱, 서버, Mac GUI 워커를 먼저 연결하기 위한 E2E 골격이다.

기본값은 `H2I_STROKE_MODE=mock`이다. 이 모드에서는 실제 OCR을 실행하지 않고 목 `crop_stroke_composite_strokes.json`을 생성한다.

## 실행

```bash
conda run -n DV python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

## 라우팅 smoke test

서버 프로세스를 띄우기 전에 목 E2E 흐름을 확인하려면 다음 명령을 실행한다.

```bash
conda run -n DV python scripts/e2e_smoke_test.py
```

## 실제 pipeline.py 사용

```bash
H2I_STROKE_MODE=pipeline conda run -n DV python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

## 주요 API

```text
POST /api/jobs
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/binary
POST /api/jobs/{job_id}/delivered

GET  /api/worker/jobs/next
GET  /api/worker/jobs/{job_id}/strokes
POST /api/worker/jobs/{job_id}/status
POST /api/worker/jobs/{job_id}/binary
POST /api/worker/jobs/{job_id}/fail
```

Mac 워커 API의 기본 토큰은 개발용 `dev-worker-token`이다. 운영 시 `H2I_WORKER_TOKEN`으로 반드시 변경해야 한다.
