"""Validated public-GitHub zip ingestion with traversal and decompression limits."""
from __future__ import annotations

import io
import re
import stat
import zipfile
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import httpx

from .scanner import SOURCE_SUFFIXES


class RepositoryError(ValueError):
    pass


def parse_github(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username or parsed.params or parsed.query or parsed.fragment or len(parts) != 2:
        raise RepositoryError("Use an HTTPS GitHub repository URL: https://github.com/owner/repo")
    owner, repo = parts
    repo = repo.removesuffix(".git")
    pattern = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not pattern.fullmatch(owner) or not pattern.fullmatch(repo) or repo in {".", ".."}:
        raise RepositoryError("The GitHub owner or repository name is invalid")
    return owner, repo


def unpack(data: bytes) -> dict[str, str]:
    if len(data) > 25_000_000:
        raise RepositoryError("Repository archive exceeds the 25 MB compressed limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise RepositoryError("GitHub returned an invalid repository archive") from exc
    files: dict[str, str] = {}
    total = 0
    with archive:
        entries = sorted(archive.infolist(), key=lambda item: item.filename)
        for entry in entries:
            if entry.is_dir():
                continue
            path = PurePosixPath(entry.filename)
            parts = path.parts[1:] if len(path.parts) > 1 else ()
            if not parts or path.is_absolute() or ".." in path.parts or "\\" in entry.filename:
                raise RepositoryError("Archive contains an unsafe path")
            if any(part in {".git", "node_modules", "dist", ".next", "__pycache__"} for part in parts):
                continue
            mode = entry.external_attr >> 16
            file_type = stat.S_IFMT(mode)
            if PurePosixPath(parts[-1]).suffix not in SOURCE_SUFFIXES or (file_type and not stat.S_ISREG(mode)):
                continue
            if entry.file_size > 1_000_000 or total + entry.file_size > 30_000_000 or len(files) >= 2000:
                raise RepositoryError("Repository exceeds source indexing limits")
            relative = PurePosixPath(*parts).as_posix()
            try:
                content = archive.read(entry).decode("utf-8")
            except (UnicodeError, RuntimeError, zipfile.BadZipFile) as exc:
                raise RepositoryError(f"Could not safely read {relative}") from exc
            files[relative] = content
            total += entry.file_size
    if not files:
        raise RepositoryError("No supported UTF-8 source files were found")
    return files


async def download_public(http: httpx.AsyncClient, url: str, token: str | None = None) -> tuple[dict, dict[str, str]]:
    owner, repo = parse_github(url)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        metadata_response = await http.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
        if metadata_response.status_code == 404:
            raise RepositoryError("Repository was not found or is not public")
        if metadata_response.status_code >= 400:
            raise RepositoryError(f"GitHub repository lookup returned HTTP {metadata_response.status_code}")
        metadata = metadata_response.json()
        if metadata.get("private"):
            raise RepositoryError("Only public repositories can be connected")
        branch = metadata.get("default_branch", "main")
        if not isinstance(branch, str) or branch.startswith("-") or ".." in branch:
            raise RepositoryError("GitHub returned an unsafe default branch")
        archive_url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{quote(branch, safe='')}"
        response = await http.get(archive_url, headers={"Accept": "application/zip"})
        if response.status_code >= 400:
            raise RepositoryError(f"GitHub archive download returned HTTP {response.status_code}")
    except (httpx.HTTPError, ValueError) as exc:
        if isinstance(exc, RepositoryError):
            raise
        raise RepositoryError(f"GitHub download failed: {type(exc).__name__}") from exc
    files = unpack(response.content)
    workspace = {
        "id": f"github-{owner}-{repo}", "name": metadata.get("name") or repo,
        "repository": f"{owner}/{repo}", "branch": branch, "environment": "Production", "source": "github",
    }
    return workspace, files
