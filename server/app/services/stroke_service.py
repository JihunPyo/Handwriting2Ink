from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path

from server.app.config import settings
from server.app.models import JobStatus
from server.app.services import job_service, storage_service


def run_stroke_extraction(job_id: str) -> None:
    job = job_service.require_job(job_id)
    input_path = Path(job["input_path"])
    output_path = storage_service.strokes_path(job_id)

    try:
        job_service.update_job(
            job_id,
            status=JobStatus.EXTRACTING_STROKES,
            message="서버에서 strokes.json을 생성하는 중입니다.",
        )

        if settings.stroke_mode == "pipeline":
            stroke_count = run_real_pipeline(job_id, input_path, output_path)
        else:
            stroke_count = write_mock_strokes(job_id, input_path, output_path)

        job_service.update_job(
            job_id,
            status=JobStatus.STROKE_READY,
            message="strokes.json이 준비되었습니다.",
            strokes_path=str(output_path),
            stroke_count=stroke_count,
        )
    except Exception as exc:
        job_service.fail_job(
            job_id,
            "STROKE_EXTRACTION_FAILED",
            str(exc),
        )


def run_real_pipeline(job_id: str, input_path: Path, output_path: Path) -> int:
    pipeline_output_dir = job_service.job_dir(job_id) / "pipeline_output"
    pipeline_output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        *shlex.split(settings.pipeline_python),
        str(settings.project_root / "pipeline.py"),
        "--input",
        str(input_path),
        "--output_dir",
        str(pipeline_output_dir),
        "--overwrite",
        "--save_stroke_data",
    ]
    subprocess.run(command, cwd=settings.project_root, check=True)

    generated_path = pipeline_output_dir / "crop_stroke_composite_strokes.json"
    if not generated_path.exists():
        raise FileNotFoundError("pipeline.py가 strokes.json을 생성하지 않았습니다.")
    shutil.copy2(generated_path, output_path)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    return int(data.get("total_stroke_count") or len(data.get("strokes", [])))


def write_mock_strokes(job_id: str, input_path: Path, output_path: Path) -> int:
    strokes = [
        {
            "id": 1,
            "region_type": "mock_text",
            "bbox": [80, 120, 360, 120],
            "point_count": 4,
            "global_points": [[80, 180], [180, 130], [300, 190], [440, 140]],
        },
        {
            "id": 2,
            "region_type": "mock_shape",
            "bbox": [120, 280, 320, 180],
            "point_count": 5,
            "global_points": [[120, 280], [440, 280], [440, 460], [120, 460], [120, 280]],
        },
        {
            "id": 3,
            "region_type": "mock_text",
            "bbox": [160, 540, 280, 80],
            "point_count": 3,
            "global_points": [[160, 580], [280, 540], [440, 610]],
        },
    ]
    payload = {
        "job_id": job_id,
        "input_path": str(input_path),
        "scale": 1.0,
        "crop_scale": 1.0,
        "region_source": "mock",
        "shape_rendering": "mock",
        "coordinate_system": {
            "global_points": "reference image coordinates",
            "point_order": "[x, y]",
        },
        "total_stroke_count": len(strokes),
        "strokes": strokes,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    run_meta = {
        "job_id": job_id,
        "mode": "mock",
        "input_path": str(input_path),
        "strokes_path": str(output_path),
    }
    (job_service.job_dir(job_id) / "run_meta.json").write_text(
        json.dumps(run_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(strokes)
