from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="서버에서 strokes.json job을 받아 GoodNotes binary를 업로드하는 Mac 워커 골격입니다."
    )
    parser.add_argument("--config", default="mac_worker/config.json", help="워커 설정 JSON 경로")
    parser.add_argument("--once", action="store_true", help="job 하나만 확인하고 종료합니다.")
    parser.add_argument(
        "--mode",
        choices=("mock", "replay"),
        default=None,
        help="mock은 fake binary를 만들고, replay는 goodnotes_controller.py를 호출합니다.",
    )
    return parser.parse_args()


def resolve_config_path(path: str) -> Path:
    return (PROJECT_ROOT / path).resolve() if not Path(path).is_absolute() else Path(path)


def merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str) -> dict[str, Any]:
    config_path = resolve_config_path(path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    local_config_path = config_path.with_name("config.local.json")
    if local_config_path.exists():
        local_config = json.loads(local_config_path.read_text(encoding="utf-8"))
        config = merge_config(config, local_config)
    if os.getenv("H2I_SERVER_URL"):
        config["server_url"] = os.environ["H2I_SERVER_URL"]
    if os.getenv("H2I_WORKER_TOKEN"):
        config["worker_token"] = os.environ["H2I_WORKER_TOKEN"]
    config["__config_path"] = str(config_path)
    return config


class WorkerClient:
    def __init__(self, config: dict[str, Any]):
        self.server_url = config["server_url"].rstrip("/") + "/"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config['worker_token']}",
                "X-Worker-Id": config.get("worker_id", "mac-worker-dev"),
            }
        )

    def url(self, path: str) -> str:
        return urljoin(self.server_url, path.lstrip("/"))

    def next_job(self) -> dict[str, Any] | None:
        response = self.session.get(self.url("/api/worker/jobs/next"), timeout=30)
        response.raise_for_status()
        return response.json().get("job")

    def download_strokes(self, strokes_url: str, output_path: Path) -> None:
        response = self.session.get(self.url(strokes_url), timeout=60)
        response.raise_for_status()
        output_path.write_bytes(response.content)

    def report_status(self, job_id: str, status: str, message: str) -> None:
        response = self.session.post(
            self.url(f"/api/worker/jobs/{job_id}/status"),
            json={"status": status, "message": message},
            timeout=30,
        )
        response.raise_for_status()

    def upload_binary(
        self,
        job_id: str,
        binary_path: Path,
        pasteboard_type: str,
    ) -> dict[str, Any]:
        with binary_path.open("rb") as file:
            response = self.session.post(
                self.url(f"/api/worker/jobs/{job_id}/binary"),
                files={"file": ("goodnotes_clipboard_item0.bin", file, "application/octet-stream")},
                data={
                    "pasteboard_type": pasteboard_type,
                    "binary_size": str(binary_path.stat().st_size),
                },
                timeout=60,
            )
        response.raise_for_status()
        return response.json()

    def fail(self, job_id: str, error_code: str, error_message: str) -> None:
        response = self.session.post(
            self.url(f"/api/worker/jobs/{job_id}/fail"),
            json={"error_code": error_code, "error_message": error_message},
            timeout=30,
        )
        response.raise_for_status()


def job_work_dir(config: dict[str, Any], job_id: str) -> Path:
    root = Path(config.get("jobs_dir", "mac_worker/jobs"))
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    path = root / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_mock_goodnotes_binary(job_id: str, strokes_path: Path, output_path: Path) -> None:
    strokes_bytes = strokes_path.read_bytes()
    digest = hashlib.sha256(strokes_bytes).hexdigest()
    payload = {
        "kind": "mock_goodnotes_clipboard_binary",
        "job_id": job_id,
        "strokes_sha256": digest,
        "note": "이 파일은 E2E 연결 확인용 목 binary입니다.",
    }
    output_path.write_bytes(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))


def should_execute_goodnotes_controller(config: dict[str, Any]) -> bool:
    return bool(config.get("execute_goodnotes_controller", config.get("execute_goodnotes_writer", False)))


def run_goodnotes_controller(config: dict[str, Any], strokes_path: Path) -> bool:
    controller_config = config.get("goodnotes_controller", {})
    if not isinstance(controller_config, dict):
        controller_config = {}

    command = [
        sys.executable,
        str(PROJECT_ROOT / "mac_worker" / "goodnotes_controller.py"),
        "--config",
        config.get("__config_path", str(PROJECT_ROOT / "mac_worker" / "config.json")),
        "--strokes",
        str(strokes_path),
    ]

    execute = should_execute_goodnotes_controller(config)
    if execute:
        command.append("--execute")

    copy_after_draw = controller_config.get("copy_after_draw", config.get("copy_after_draw", True))
    if copy_after_draw:
        command.append("--copy_after_draw")

    if controller_config.get("skip_fullscreen", config.get("skip_fullscreen", False)):
        command.append("--skip_fullscreen")
    if controller_config.get("skip_pen_select", config.get("skip_pen_select", False)):
        command.append("--skip_pen_select")

    try:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        if exc.returncode in {130, -2}:
            raise KeyboardInterrupt from exc
        raise
    return execute


def dump_goodnotes_clipboard(output_path: Path) -> None:
    script_path = PROJECT_ROOT / "mac_worker" / "dump_goodnotes_clipboard.swift"
    env = os.environ.copy()
    env.setdefault("CLANG_MODULE_CACHE_PATH", "/private/tmp/h2i_clang_module_cache")
    subprocess.run(
        ["swift", str(script_path), str(output_path)],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )


def process_job(client: WorkerClient, config: dict[str, Any], job: dict[str, Any]) -> None:
    job_id = job["job_id"]
    work_dir = job_work_dir(config, job_id)
    strokes_path = work_dir / "strokes.json"
    binary_path = work_dir / "goodnotes_clipboard_item0.bin"

    client.report_status(job_id, "drawing_in_goodnotes", "Mac 워커가 strokes.json을 다운로드합니다.")
    client.download_strokes(job["strokes_url"], strokes_path)

    mode = config.get("mode", "mock")
    if mode == "replay":
        client.report_status(job_id, "drawing_in_goodnotes", "GoodNotes에 stroke를 그리고 올가미로 복사합니다.")
        executed = run_goodnotes_controller(config, strokes_path)
        if not executed:
            raise RuntimeError(
                "execute_goodnotes_controller=false 상태에서는 실제 GoodNotes 복사 결과가 없어 binary 추출을 중단합니다."
            )
        client.report_status(job_id, "copying_from_goodnotes", "GoodNotes pasteboard binary를 추출합니다.")
        dump_goodnotes_clipboard(binary_path)
    else:
        client.report_status(job_id, "drawing_in_goodnotes", "목 모드에서 GoodNotes 그리기를 시뮬레이션합니다.")
        time.sleep(0.5)
        client.report_status(job_id, "copying_from_goodnotes", "목 모드에서 pasteboard 추출을 시뮬레이션합니다.")
        make_mock_goodnotes_binary(job_id, strokes_path, binary_path)

    result = client.upload_binary(
        job_id,
        binary_path,
        config.get("pasteboard_type", "com.goodnotesapp.goodnotes5.notes"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    if args.mode:
        config["mode"] = args.mode

    client = WorkerClient(config)
    poll_interval = float(config.get("poll_interval_seconds", 3))

    while True:
        job = client.next_job()
        if job is None:
            print("처리할 job이 없습니다.")
            if args.once:
                return
            time.sleep(poll_interval)
            continue

        try:
            process_job(client, config, job)
        except KeyboardInterrupt:
            print("사용자 인터럽트로 Mac 워커를 중단했습니다.")
            raise
        except Exception as exc:
            client.fail(job["job_id"], "MAC_WORKER_FAILED", str(exc))
            raise

        if args.once:
            return


if __name__ == "__main__":
    main()
