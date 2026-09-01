from __future__ import annotations

from fastapi import FastAPI

from backend.app.api import jobs, worker
from backend.app.config import settings


app = FastAPI(
    title="H2I GoodNotes Restore Server",
    version="0.1.0",
    description="iPad 업로드, strokes.json 생성, Mac 워커 binary 업로드를 연결하는 E2E 서버 골격입니다.",
)

app.include_router(jobs.router)
app.include_router(worker.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "storage_root": str(settings.storage_root),
        "stroke_mode": settings.stroke_mode,
    }
