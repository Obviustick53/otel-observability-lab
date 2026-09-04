"""Small dependency-free smoke test for a running data-service."""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


BASE_URL = os.getenv("DATA_SERVICE_URL", "http://localhost:8002").rstrip("/")
RECORD_ID = os.getenv("DATA_SERVICE_RECORD_ID", "ord-001")


def get_json(path: str) -> tuple[int, dict]:
    try:
        with urlopen(f"{BASE_URL}{path}", timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"data-service is unreachable at {BASE_URL}: {exc.reason}") from exc


def main() -> int:
    health_status, health_body = get_json("/health")
    data_status, data_body = get_json(f"/data/{RECORD_ID}")
    print(json.dumps({"base_url": BASE_URL, "health": {"status": health_status, "body": health_body}, "data": {"status": data_status, "body": data_body}}, indent=2, sort_keys=True))
    if health_status != 200 or health_body.get("status") != "ok":
        return 1
    if data_status not in {200, 404}:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
