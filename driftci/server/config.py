"""Environment-backed settings; importing this module never reads secrets or opens sockets."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: str
    contextdev_api_key: str | None
    github_token: str | None
    offline: bool
    context_cache_ttl: int
    osv_cache_ttl: int
    kev_cache_ttl: int
    context_min_interval: float
    request_timeout: float
    web_dist: Path
    example_dir: Path
    watch_interval_seconds: int = 0
    scan_cooldown_seconds: int = 0
    github_file_limit: int = 600
    github_byte_limit: int = 12_000_000
    github_file_byte_limit: int = 2_000_000

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(__file__).resolve().parents[1]
        state = Path(os.environ.get("DRIFTCI_STATE_DIR", root / ".driftci"))
        return cls(
            db_path=os.environ.get("DRIFTCI_DB_PATH", str(state / "driftci.db")),
            contextdev_api_key=os.environ.get("CONTEXTDEV_API_KEY") or None,
            github_token=os.environ.get("GITHUB_TOKEN") or None,
            offline=os.environ.get("DRIFTCI_OFFLINE", "").lower() in {"1", "true", "yes"},
            context_cache_ttl=int(os.environ.get("DRIFTCI_CONTEXT_CACHE_TTL", "21600")),
            osv_cache_ttl=int(os.environ.get("DRIFTCI_OSV_CACHE_TTL", "3600")),
            kev_cache_ttl=int(os.environ.get("DRIFTCI_KEV_CACHE_TTL", "21600")),
            context_min_interval=float(os.environ.get("CONTEXTDEV_MIN_INTERVAL", "6.2")),
            request_timeout=float(os.environ.get("DRIFTCI_HTTP_TIMEOUT", "25")),
            web_dist=Path(os.environ.get("DRIFTCI_WEB_DIST", root / "web" / "dist")),
            example_dir=Path(os.environ.get("DRIFTCI_EXAMPLE_DIR", root / "examples" / "orders-ai")),
            watch_interval_seconds=int(os.environ.get("DRIFTCI_WATCH_INTERVAL_SECONDS", "0")),
            scan_cooldown_seconds=int(os.environ.get("DRIFTCI_SCAN_COOLDOWN_SECONDS", "0")),
            github_file_limit=int(os.environ.get("DRIFTCI_GITHUB_FILE_LIMIT", "600")),
            github_byte_limit=int(os.environ.get("DRIFTCI_GITHUB_BYTE_LIMIT", "12000000")),
            github_file_byte_limit=int(os.environ.get("DRIFTCI_GITHUB_FILE_BYTE_LIMIT", "2000000")),
        )
