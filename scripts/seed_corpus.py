"""Seed the running API with the bundled sample documentation corpus
(`eval/golden_corpus/`, 8 fictional company policy docs) so a reviewer can
`docker compose up` and immediately ask real questions with no manual setup
step.

Talks to the API over plain HTTP using only the standard library (no extra
dependency for a one-off startup script). Waits for `/health` to respond
before ingesting, since this runs as its own docker-compose service that
starts alongside (not strictly after) the API container finishing startup.

Usage:
    python scripts/seed_corpus.py
    SEED_API_URL=http://localhost:8000 python scripts/seed_corpus.py   # against a locally-run (non-docker) API
"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API_URL = os.environ.get("SEED_API_URL", "http://api:8000")
CORPUS_DIR = Path(__file__).resolve().parent.parent / "eval" / "golden_corpus"
HEALTH_TIMEOUT_SECONDS = 90


def wait_for_health(url: str, timeout: float) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=3) as resp:
                if resp.status == 200:
                    print(f"API is healthy at {url}")
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
        time.sleep(2)
    raise SystemExit(f"API at {url} did not become healthy within {timeout:.0f}s (last error: {last_error})")


def _multipart_body(paths: list[Path]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for path in paths:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        parts.append(
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="files"; filename="{path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n".encode()
            + path.read_bytes()
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(p if isinstance(p, bytes) else p.encode() for p in parts)
    return body, f"multipart/form-data; boundary={boundary}"


def already_seeded(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/v1/documents", timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("total_chunks", 0) > 0
    except Exception:  # noqa: BLE001 - if this check fails for any reason, just proceed to seed
        return False


def seed(url: str = API_URL, corpus_dir: Path = CORPUS_DIR) -> None:
    wait_for_health(url, HEALTH_TIMEOUT_SECONDS)

    if already_seeded(url):
        print("Index already has content -- skipping seed (safe to re-run; nothing is duplicated either way "
              "thanks to dedup, but no need to repeat the work).")
        return

    doc_paths = sorted(corpus_dir.glob("*.md"))
    if not doc_paths:
        raise SystemExit(f"No documents found in {corpus_dir}")

    print(f"Ingesting {len(doc_paths)} sample document(s) from {corpus_dir}...")
    body, content_type = _multipart_body(doc_paths)
    request = urllib.request.Request(
        f"{url}/v1/ingest", data=body, method="POST", headers={"Content-Type": content_type}
    )
    with urllib.request.urlopen(request, timeout=120) as resp:
        result = json.loads(resp.read())

    for report in result["reports"]:
        if report["error"]:
            print(f"  {report['source_file']}: ERROR - {report['error']}")
        else:
            print(f"  {report['source_file']}: {report['chunks_inserted']} chunks inserted")

    print("\nSeed complete. Try asking a question, e.g.:")
    print('  curl -X POST localhost:8000/v1/ask -H "Content-Type: application/json" \\')
    print('    -d \'{"question": "How many vacation days do employees accrue per month?"}\'')


if __name__ == "__main__":
    try:
        seed()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - top-level: report and exit non-zero, don't crash silently
        print(f"Seeding failed: {exc}", file=sys.stderr)
        sys.exit(1)
