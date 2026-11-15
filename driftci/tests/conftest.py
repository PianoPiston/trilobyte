from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app import create_app  # noqa: E402
from server.config import Settings  # noqa: E402

EXAMPLE = ROOT / "examples" / "orders-ai"


def make_settings(tmp_path: Path, **changes) -> Settings:
    values = dict(
        db_path=str(tmp_path / "test.db"), contextdev_api_key=None, github_token=None,
        offline=True, context_cache_ttl=21600, osv_cache_ttl=3600, kev_cache_ttl=21600,
        context_min_interval=0, request_timeout=2, web_dist=tmp_path / "no-web", example_dir=EXAMPLE,
    )
    values.update(changes)
    return Settings(**values)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(make_settings(tmp_path))) as test_client:
        yield test_client
