"""Cached HTTP with per-host pacing, bounded retries and stale-on-error behavior."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from .db import Database


@dataclass
class WebResult:
    data: Any = None
    mode: str = "live"
    retrieved_at: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.data is not None and self.error is None


class CachedWebClient:
    def __init__(self, db: Database, http: httpx.AsyncClient, min_interval: float = .2, attempts: int = 2):
        self.db = db
        self.http = http
        self.min_interval = min_interval
        self.attempts = attempts
        self._slots: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def _pace(self, url: str) -> None:
        host = urlparse(url).hostname or "unknown"
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = self._slots.get(host, 0) - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._slots[host] = time.monotonic() + self.min_interval

    async def request_json(self, method: str, url: str, cache_key: str, ttl: int, *, payload: dict | None = None, headers: dict[str, str] | None = None) -> WebResult:
        now = time.time()
        cached = self.db.cache_get(cache_key) if self.db.cache_fetched_at(cache_key) + ttl >= now else None
        if cached is not None:
            return WebResult(cached.get("body"), "cached", cached.get("retrieved_at"))
        error = "Request failed"
        for attempt in range(self.attempts):
            await self._pace(url)
            try:
                response = await self.http.request(method, url, json=payload, headers=headers)
                if response.status_code == 429 or response.status_code >= 500:
                    error = f"HTTP {response.status_code} from {urlparse(url).hostname}"
                    if attempt + 1 < self.attempts:
                        retry_after = response.headers.get("Retry-After")
                        try:
                            delay = min(60, max(0, float(retry_after))) if retry_after else 2 ** attempt
                        except ValueError:
                            delay = 2 ** attempt
                        await asyncio.sleep(delay)
                        continue
                elif response.status_code >= 400:
                    error = f"HTTP {response.status_code} from {urlparse(url).hostname}"
                else:
                    body = response.json()
                    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
                    self.db.cache_set(cache_key, time.time(), {"body": body, "retrieved_at": retrieved_at})
                    return WebResult(body, "live", retrieved_at)
            except (httpx.HTTPError, ValueError) as exc:
                error = f"{urlparse(url).hostname}: {type(exc).__name__}"
                if attempt + 1 < self.attempts:
                    await asyncio.sleep(2 ** attempt)
                    continue
            break
        stale = self.db.cache_get(cache_key)
        if stale is not None:
            return WebResult(stale.get("body"), "cached", stale.get("retrieved_at"), error)
        return WebResult(error=error)
