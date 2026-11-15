from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def stable_id(prefix: str, *parts: str, length: int = 16) -> str:
    digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()[:length]
    return f"{prefix}-{digest}"


def safe_excerpt(value: object, limit: int = 500) -> str:
    """Treat remote text as data: decode entities, remove markup/control characters and cap it."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"(?is)<(script|style|svg)\b[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = "".join(char if char.isprintable() else " " for char in text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def sanitize_markdown(value: object, limit: int = 250_000) -> str:
    """Keep line structure for deterministic parsers while neutralizing embedded HTML/control bytes."""
    text = html.unescape(str(value or "")).replace("\x00", "")
    text = re.sub(r"(?is)<(script|style|svg)\b[^>]*>.*?</\1>", "", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    lines = []
    for line in text.splitlines():
        cleaned = "".join(char if char.isprintable() or char == "\t" else " " for char in line)
        lines.append(cleaned[:4000])
    return "\n".join(lines)[:limit]


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
