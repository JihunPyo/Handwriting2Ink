from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from server.app.config import settings
from server.app.models import JobStatus
from server.app.services import job_service, storage_service

router = APIRouter(prefix="/api/worker/jobs", tags=["Mac worker"])


class WorkerStatusRequest(BaseModel):
    status: JobStatus
    message: str | None = None


class WorkerFailRequest(BaseModel):
    error_code: str
    error_message: str


def require_worker_token(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {settings.worker_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="worker token이 유효하지 않습니다.")


@router.get("/next", dependencies=[Depends(require_worker_token)])
async def next_job(x_worker_id: str | None = Header(default=None)) -> dict[str, object]:
    worker_id = x_worker_id or "mac-worker-dev"
    job = job_service.claim_next_stroke_ready(worker_id)
    if job is None:
        return {"job": None}
    return {
        "job": {
            "job_id": job["job_id"],
            "status": job["status"],
            "strokes_url": f"/api/worker/jobs/{job['job_id']}/strokes",
        }
    }


@router.get("/{job_id}/strokes", dependencies=[Depends(require_worker_token)])
async def download_strokes(job_id: str) -> FileResponse:
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job을 찾을 수 없습니다.")
    strokes_path = job.get("strokes_path")
    if not strokes_path or not Path(strokes_path).exists():
        raise HTTPException(status_code=404, detail="strokes.json이 아직 준비되지 않았습니다.")
    return FileResponse(strokes_path, media_type="application/json", filename="strokes.json")


@router.post("/{job_id}/status", dependencies=[Depends(require_worker_token)])
async def report_status(job_id: str, payload: WorkerStatusRequest) -> dict[str, str]:
    if job_service.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job을 찾을 수 없습니다.")
    job = job_service.update_job(
        job_id,
        status=payload.status,
        message=payload.message or "Mac 워커가 상태를 보고했습니다.",
    )
    return {"job_id": job["job_id"], "status": job["status"]}


@router.post("/{job_id}/binary", dependencies=[Depends(require_worker_token)])
async def upload_binary(
    job_id: str,
    file: UploadFile = File(...),
    pasteboard_type: str = Form(default=settings.pasteboard_type),
    binary_size: int | None = Form(default=None),
) -> dict[str, object]:
    if job_service.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job을 찾을 수 없습니다.")

    job_service.update_job(
        job_id,
        status=JobStatus.UPLOADING_BINARY,
        message="Mac 워커가 GoodNotes binary를 업로드하는 중입니다.",
    )
    output_path = storage_service.binary_path(job_id)
    with output_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    size = binary_size if binary_size is not None else output_path.stat().st_size
    job = job_service.update_job(
        job_id,
        status=JobStatus.BIN_READY,
        message="GoodNotes binary가 준비되었습니다.",
        binary_path=str(output_path),
        pasteboard_type=pasteboard_type,
        binary_size=size,
    )
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "binary_size": job["binary_size"],
        "pasteboard_type": job["pasteboard_type"],
    }


@router.post("/{job_id}/fail", dependencies=[Depends(require_worker_token)])
async def report_failure(job_id: str, payload: WorkerFailRequest) -> dict[str, str]:
    if job_service.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job을 찾을 수 없습니다.")
    job = job_service.fail_job(job_id, payload.error_code, payload.error_message)
    return {"job_id": job["job_id"], "status": job["status"]}

