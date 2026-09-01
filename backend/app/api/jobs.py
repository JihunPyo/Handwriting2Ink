from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.models import JobStatus
from backend.app.services import job_service, storage_service, stroke_service

router = APIRouter(prefix="/api/jobs", tags=["iPad jobs"])


@router.post("")
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict[str, str]:
    job = job_service.create_job()
    input_path = storage_service.save_uploaded_image(
        job["job_id"],
        filename=file.filename,
        content_type=file.content_type,
        file=file.file,
    )
    job_service.update_job(
        job["job_id"],
        status=JobStatus.UPLOADED,
        message="이미지가 업로드되었습니다.",
        input_filename=file.filename,
        input_path=str(input_path),
    )
    background_tasks.add_task(stroke_service.run_stroke_extraction, job["job_id"])
    return {"job_id": job["job_id"], "status": JobStatus.UPLOADED}


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job을 찾을 수 없습니다.")
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "message": job.get("message"),
        "binary_ready": bool(job.get("binary_path")),
        "strokes_ready": bool(job.get("strokes_path")),
        "error_code": job.get("error_code"),
        "error_message": job.get("error_message"),
    }


@router.get("/{job_id}/binary")
async def download_binary(job_id: str) -> FileResponse:
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job을 찾을 수 없습니다.")

    binary_path = job.get("binary_path")
    if not binary_path or not Path(binary_path).exists():
        raise HTTPException(status_code=404, detail="binary가 아직 준비되지 않았습니다.")

    return FileResponse(
        binary_path,
        media_type="application/octet-stream",
        filename="goodnotes_clipboard_item0.bin",
    )


@router.post("/{job_id}/delivered")
async def mark_delivered(job_id: str) -> dict[str, str]:
    if job_service.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="job을 찾을 수 없습니다.")
    job = job_service.update_job(
        job_id,
        status=JobStatus.DELIVERED,
        message="iPad 앱이 binary를 수신했습니다.",
    )
    return {"job_id": job["job_id"], "status": job["status"]}
