from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

WORKER_TOKEN = "dev-worker-token"
PASTEBOARD_TYPE = "com.goodnotesapp.goodnotes5.notes"
MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def require_ok(response: Any, label: str) -> None:
    if 200 <= response.status_code < 300:
        return
    raise RuntimeError(f"{label} 실패: HTTP {response.status_code} {response.text}")


def print_step(number: int, label: str, payload: dict[str, Any] | None = None) -> None:
    print(f"[{number}] {label}")
    if payload is not None:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def wait_until_stroke_ready(client: TestClient, job_id: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_payload: dict[str, Any] | None = None

    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        require_ok(response, "job 상태 조회")
        payload = response.json()
        last_payload = payload
        if payload["status"] in {"stroke_ready", "failed"}:
            return payload
        time.sleep(0.1)

    raise TimeoutError(f"stroke_ready 대기 시간이 초과되었다: {last_payload}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="h2i_e2e_") as storage_root:
        os.environ["H2I_STORAGE_ROOT"] = storage_root
        os.environ["H2I_STROKE_MODE"] = "mock"
        os.environ["H2I_WORKER_TOKEN"] = WORKER_TOKEN

        from server.app.main import app

        client = TestClient(app)
        worker_headers = {
            "Authorization": f"Bearer {WORKER_TOKEN}",
            "X-Worker-Id": "smoke-test-worker",
        }

        response = client.get("/health")
        require_ok(response, "health 확인")
        print_step(1, "서버 health 확인", response.json())

        response = client.post(
            "/api/jobs",
            files={"file": ("input.png", MINIMAL_PNG, "image/png")},
        )
        require_ok(response, "이미지 업로드")
        created = response.json()
        job_id = created["job_id"]
        print_step(2, "iPad 업로드 API 확인", created)

        status_payload = wait_until_stroke_ready(client, job_id)
        if status_payload["status"] == "failed":
            raise RuntimeError(f"stroke 생성 실패: {status_payload}")
        print_step(3, "서버 strokes.json 생성 확인", status_payload)

        response = client.get("/api/worker/jobs/next", headers=worker_headers)
        require_ok(response, "worker job claim")
        claimed = response.json()["job"]
        if not claimed or claimed["job_id"] != job_id:
            raise RuntimeError(f"예상 job을 claim하지 못했다: {claimed}")
        print_step(4, "Mac 워커 job claim 확인", claimed)

        response = client.get(claimed["strokes_url"], headers=worker_headers)
        require_ok(response, "strokes 다운로드")
        strokes_payload = response.json()
        print_step(
            5,
            "Mac 워커 strokes.json 다운로드 확인",
            {"total_stroke_count": strokes_payload["total_stroke_count"]},
        )

        response = client.post(
            f"/api/worker/jobs/{job_id}/status",
            headers=worker_headers,
            json={
                "status": "drawing_in_goodnotes",
                "message": "smoke test에서 GoodNotes 재생 단계를 통과 처리했다.",
            },
        )
        require_ok(response, "worker 상태 보고")
        print_step(6, "Mac 워커 상태 보고 확인", response.json())

        mock_binary = b"mock-goodnotes-binary-for-e2e-smoke-test"
        response = client.post(
            f"/api/worker/jobs/{job_id}/binary",
            headers=worker_headers,
            files={
                "file": (
                    "goodnotes_clipboard_item0.bin",
                    mock_binary,
                    "application/octet-stream",
                )
            },
            data={
                "pasteboard_type": PASTEBOARD_TYPE,
                "binary_size": str(len(mock_binary)),
            },
        )
        require_ok(response, "worker binary 업로드")
        print_step(7, "Mac 워커 binary 업로드 확인", response.json())

        response = client.get(f"/api/jobs/{job_id}/binary")
        require_ok(response, "iPad binary 다운로드")
        if response.content != mock_binary:
            raise RuntimeError("다운로드한 binary 내용이 업로드한 내용과 다르다.")
        print_step(8, "iPad binary 다운로드 확인", {"binary_size": len(response.content)})

        response = client.post(f"/api/jobs/{job_id}/delivered")
        require_ok(response, "delivered 상태 보고")
        print_step(9, "iPad delivered 상태 보고 확인", response.json())

    print("[done] 목 E2E 연결 확인을 완료했다.")


if __name__ == "__main__":
    main()
