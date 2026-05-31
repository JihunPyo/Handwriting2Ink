from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    server_root: Path
    storage_root: Path
    worker_token: str
    pasteboard_type: str
    stroke_mode: str
    pipeline_python: str


def load_settings() -> Settings:
    server_root = Path(__file__).resolve().parents[1]
    project_root = server_root.parent
    storage_root = Path(
        os.getenv("H2I_STORAGE_ROOT", str(server_root / "storage"))
    ).resolve()

    return Settings(
        project_root=project_root,
        server_root=server_root,
        storage_root=storage_root,
        worker_token=os.getenv("H2I_WORKER_TOKEN", "dev-worker-token"),
        pasteboard_type=os.getenv(
            "H2I_GOODNOTES_PASTEBOARD_TYPE",
            "com.goodnotesapp.goodnotes5.notes",
        ),
        stroke_mode=os.getenv("H2I_STROKE_MODE", "mock"),
        pipeline_python=os.getenv("H2I_PIPELINE_PYTHON", sys.executable),
    )


settings = load_settings()

