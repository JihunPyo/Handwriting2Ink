from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO

from backend.app.services import job_service


def safe_extension(filename: str | None, content_type: str | None) -> str:
    if filename:
        suffix = Path(filename).suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            return suffix
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    return ".jpg"


def save_uploaded_image(
    job_id: str,
    *,
    filename: str | None,
    content_type: str | None,
    file: BinaryIO,
) -> Path:
    extension = safe_extension(filename, content_type)
    output_path = job_service.job_dir(job_id) / f"input{extension}"
    with output_path.open("wb") as target:
        shutil.copyfileobj(file, target)
    return output_path


def strokes_path(job_id: str) -> Path:
    return job_service.job_dir(job_id) / "crop_stroke_composite_strokes.json"


def binary_path(job_id: str) -> Path:
    return job_service.job_dir(job_id) / "goodnotes_clipboard_item0.bin"
