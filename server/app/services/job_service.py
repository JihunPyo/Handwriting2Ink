from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.app.config import settings
from server.app.models import JobStatus


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def job_root() -> Path:
    return settings.storage_root / "jobs"


def job_dir(job_id: str) -> Path:
    return job_root() / job_id


def job_json_path(job_id: str) -> Path:
    return job_dir(job_id) / "job.json"


def events_path(job_id: str) -> Path:
    return job_dir(job_id) / "events.jsonl"


def create_job() -> dict[str, Any]:
    job_id = f"job_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    created_at = utc_now()
    path = job_dir(job_id)
    path.mkdir(parents=True, exist_ok=False)

    job = {
        "job_id": job_id,
        "status": JobStatus.CREATED,
        "message": "job이 생성되었습니다.",
        "input_filename": None,
        "input_path": None,
        "output_dir": str(path),
        "strokes_path": None,
        "binary_path": None,
        "pasteboard_type": None,
        "binary_size": None,
        "stroke_count": None,
        "assigned_worker_id": None,
        "error_code": None,
        "error_message": None,
        "created_at": created_at,
        "updated_at": created_at,
    }
    save_job(job)
    add_event(job_id, JobStatus.CREATED, "job이 생성되었습니다.")
    return job


def save_job(job: dict[str, Any]) -> None:
    job["updated_at"] = utc_now()
    path = job_json_path(job["job_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(job, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def get_job(job_id: str) -> dict[str, Any] | None:
    path = job_json_path(job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def require_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if job is None:
        raise FileNotFoundError(f"job을 찾을 수 없습니다: {job_id}")
    return job


def add_event(job_id: str, status: str, message: str | None = None) -> None:
    path = events_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "job_id": job_id,
        "status": str(status),
        "message": message,
        "created_at": utc_now(),
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")


def update_job(
    job_id: str,
    *,
    status: str | JobStatus | None = None,
    message: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    job = require_job(job_id)
    if status is not None:
        job["status"] = str(status)
    if message is not None:
        job["message"] = message
    for key, value in fields.items():
        job[key] = value
    save_job(job)
    if status is not None or message is not None:
        add_event(job_id, job["status"], message)
    return job


def fail_job(job_id: str, error_code: str, error_message: str) -> dict[str, Any]:
    return update_job(
        job_id,
        status=JobStatus.FAILED,
        message="작업 처리에 실패했습니다.",
        error_code=error_code,
        error_message=error_message,
    )


def list_jobs() -> list[dict[str, Any]]:
    root = job_root()
    if not root.exists():
        return []
    jobs = []
    for path in sorted(root.glob("job_*/job.json")):
        try:
            jobs.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return jobs


def claim_next_stroke_ready(worker_id: str) -> dict[str, Any] | None:
    for job in list_jobs():
        if job.get("status") != JobStatus.STROKE_READY:
            continue
        return update_job(
            job["job_id"],
            status=JobStatus.ASSIGNED_TO_WORKER,
            message="Mac 워커가 작업을 가져갔습니다.",
            assigned_worker_id=worker_id,
        )
    return None

