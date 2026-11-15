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
    context_daily_credit_limit: int
    context_max_sources: int
    request_timeout: float
    web_dist: Path
    example_dir: Path
    watch_interval_seconds: int = 0
    scan_cooldown_seconds: int = 0
    github_file_limit: int = 120
    github_byte_limit: int = 4_000_000
    github_file_byte_limit: int = 1_000_000
    repository_connect_timeout_seconds: int = 90
    vulnerability_package_limit: int = 32
    osv_batch_timeout_seconds: int = 25
    release_webhook_secret: str | None = None
    release_poll_interval_seconds: int = 90
    release_manual_cooldown_seconds: int = 10
    release_detail_limit: int = 2
    status_cache_ttl_seconds: int = 300
    status_hot_ttl_seconds: int = 45
    status_hot_window_seconds: int = 900

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
            context_daily_credit_limit=int(os.environ.get("CONTEXTDEV_DAILY_CREDIT_LIMIT", "80")),
            context_max_sources=min(12, max(1, int(os.environ.get("CONTEXTDEV_MAX_SOURCES", "6")))),
            request_timeout=float(os.environ.get("DRIFTCI_HTTP_TIMEOUT", "25")),
            web_dist=Path(os.environ.get("DRIFTCI_WEB_DIST", root / "web" / "dist")),
            example_dir=Path(os.environ.get("DRIFTCI_EXAMPLE_DIR", root / "examples" / "orders-ai")),
            watch_interval_seconds=int(os.environ.get("DRIFTCI_WATCH_INTERVAL_SECONDS", "0")),
            scan_cooldown_seconds=int(os.environ.get("DRIFTCI_SCAN_COOLDOWN_SECONDS", "0")),
            github_file_limit=int(os.environ.get("DRIFTCI_GITHUB_FILE_LIMIT", "120")),
            github_byte_limit=int(os.environ.get("DRIFTCI_GITHUB_BYTE_LIMIT", "4000000")),
            github_file_byte_limit=int(os.environ.get("DRIFTCI_GITHUB_FILE_BYTE_LIMIT", "1000000")),
            repository_connect_timeout_seconds=int(os.environ.get("DRIFTCI_REPOSITORY_CONNECT_TIMEOUT_SECONDS", "90")),
            vulnerability_package_limit=int(os.environ.get("DRIFTCI_OSV_PACKAGE_LIMIT", "32")),
            osv_batch_timeout_seconds=int(os.environ.get("DRIFTCI_OSV_BATCH_SECONDS", "25")),
            release_webhook_secret=os.environ.get("DRIFTCI_GITHUB_WEBHOOK_SECRET") or None,
            release_poll_interval_seconds=max(0, int(os.environ.get("DRIFTCI_RELEASE_POLL_SECONDS", "90"))),
            release_manual_cooldown_seconds=max(0, int(os.environ.get("DRIFTCI_RELEASE_MANUAL_COOLDOWN_SECONDS", "10"))),
            release_detail_limit=min(5, max(0, int(os.environ.get("DRIFTCI_RELEASE_DETAIL_LIMIT", "2")))),
            status_cache_ttl_seconds=max(60, int(os.environ.get("DRIFTCI_STATUS_CACHE_TTL", "300"))),
            status_hot_ttl_seconds=max(30, int(os.environ.get("DRIFTCI_STATUS_HOT_CACHE_TTL", "45"))),
            status_hot_window_seconds=max(60, int(os.environ.get("DRIFTCI_STATUS_HOT_WINDOW_SECONDS", "900"))),
        )
