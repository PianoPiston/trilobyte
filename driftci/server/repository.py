"""Selective public-GitHub source reading; no archive, clone or repository execution.

A recursive tree identifies relevant manifests and source/config files. Only those
files are read from raw.githubusercontent.com, pinned to an immutable commit SHA.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import httpx

from .scanner import CONFIG_SUFFIXES, MANIFEST_NAMES


class RepositoryError(ValueError):
    pass


@dataclass(frozen=True)
class SourceLimits:
    """Limits on selected text reads, deliberately not a total repository limit."""

    max_files: int = 64
    max_bytes: int = 2_000_000
    max_file_bytes: int = 1_000_000
    concurrency: int = 8
    max_seconds: int = 25
    per_file_timeout: int = 6

    def __post_init__(self) -> None:
        if not 1 <= self.max_files <= 2000 or not 100_000 <= self.max_bytes <= 40_000_000:
            raise ValueError("Invalid GitHub source-reading limits")
        if not 10_000 <= self.max_file_bytes <= 10_000_000 or not 1 <= self.concurrency <= 8:
            raise ValueError("Invalid GitHub file/concurrency limits")
        if not 5 <= self.max_seconds <= 120 or not 1 <= self.per_file_timeout <= 30:
            raise ValueError("Invalid GitHub source-reading deadlines")


IGNORED_DIRECTORIES = {
    ".git", ".next", ".svn", ".hg", "__pycache__", "node_modules", "bower_components",
    "dist", "build", "coverage", "target", "vendor", "venv", ".venv", ".tox",
    ".gradle", ".terraform", ".idea", ".vscode", ".cache",
    "test", "tests", "fixtures", "testdata", "test_data", "__mocks__", "docs", "documentation",
}
SAFE_SHA = re.compile(r"^[0-9a-fA-F]{40,64}$")
SAFE_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}")


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


def safe_relative_path(value: object) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    if len(value) > 1000:
        return None
    return path.as_posix()


def supported_source(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if any(part in IGNORED_DIRECTORIES for part in parts):
        return False
    name = parts[-1]
    # Documentation and media are intentionally not downloaded. Requirements and
    # other named manifests are handled before the extension allowlist.
    return name in MANIFEST_NAMES or PurePosixPath(name).suffix.lower() in CONFIG_SUFFIXES


def candidate_priority(path: str) -> tuple[int, int, str]:
    name = PurePosixPath(path).name
    depth = len(PurePosixPath(path).parts)
    if name in MANIFEST_NAMES:
        return 0, depth, path
    if any(part in {"src", "app", "lib", "server", "api", "config"} for part in PurePosixPath(path).parts[:-1]):
        return 1, depth, path
    return 2, depth, path


async def _api_json(http: httpx.AsyncClient, url: str, headers: dict[str, str], label: str) -> dict:
    try:
        response = await http.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise RepositoryError(f"GitHub {label} request failed: {type(exc).__name__}") from exc
    if response.status_code == 404:
        raise RepositoryError("Repository/default branch not found, or access is not public")
    if response.status_code in {403, 429}:
        raise RepositoryError("GitHub API rate limit reached. Retry later or configure a least-privilege GitHub token.")
    if response.status_code >= 400:
        raise RepositoryError(f"GitHub {label} request returned HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError as exc:
        raise RepositoryError(f"GitHub returned invalid {label} metadata") from exc
    if not isinstance(data, dict):
        raise RepositoryError(f"GitHub returned invalid {label} metadata")
    return data


async def read_public(
    http: httpx.AsyncClient,
    url: str,
    token: str | None = None,
    limits: SourceLimits | None = None,
) -> tuple[dict, dict[str, str]]:
    """Read a bounded, relevant text subset of a public repository of any size.

    GitHub API credentials are used only for api.github.com metadata. Raw source
    requests are public, credential-free and pinned to the resolved commit SHA.
    """
    limits = limits or SourceLimits()
    owner, repo = parse_github(url)
    api_headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        api_headers["Authorization"] = f"Bearer {token}"
    root = f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
    metadata = await _api_json(http, root, api_headers, "repository")
    if metadata.get("private"):
        raise RepositoryError("Only public repositories can be connected")
    branch = metadata.get("default_branch", "main")
    if not isinstance(branch, str) or not SAFE_BRANCH.fullmatch(branch) or ".." in branch or branch.startswith("-"):
        raise RepositoryError("GitHub returned an unsafe default branch")
    encoded_branch = quote(branch, safe="")
    reference = await _api_json(http, f"{root}/git/ref/heads/{encoded_branch}", api_headers, "branch")
    commit = (reference.get("object") or {}).get("sha")
    if not isinstance(commit, str) or not SAFE_SHA.fullmatch(commit):
        raise RepositoryError("GitHub did not return a valid commit for this repository")
    tree = await _api_json(http, f"{root}/git/trees/{commit}?recursive=1", api_headers, "source tree")
    entries = tree.get("tree")
    if not isinstance(entries, list):
        raise RepositoryError("GitHub returned an invalid source-tree listing")

    candidates: list[tuple[str, int]] = []
    seen: set[str] = set()
    repository_files = 0
    ignored_metadata_paths = 0
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") != "blob":
            continue
        repository_files += 1
        path = safe_relative_path(entry.get("path"))
        if not path:
            ignored_metadata_paths += 1
            continue
        if path in seen or not supported_source(path):
            continue
        size = entry.get("size", 0)
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            continue
        seen.add(path)
        candidates.append((path, size))
    candidates.sort(key=lambda item: candidate_priority(item[0]))

    selected: list[tuple[str, int]] = []
    budget = 0
    skipped_large = 0
    skipped_budget = 0
    for path, size in candidates:
        if size > limits.max_file_bytes:
            skipped_large += 1
            continue
        # Every read is bounded. Manifest-first ordering gives dependency
        # manifests priority before application files consume a shared budget.
        if len(selected) >= limits.max_files or budget + size > limits.max_bytes:
            skipped_budget += 1
            continue
        selected.append((path, size))
        budget += size

    semaphore = asyncio.Semaphore(limits.concurrency)
    errors: list[str] = []
    read_started = asyncio.get_running_loop().time()

    async def fetch(path: str) -> tuple[str, str, int] | None:
        raw_url = f"https://raw.githubusercontent.com/{quote(owner, safe='')}/{quote(repo, safe='')}/{commit}/{quote(path, safe='/')}"
        try:
            body = bytearray()
            async with semaphore, asyncio.timeout(limits.per_file_timeout):
                # Per-file network IO is bounded independently of the shared deadline.
                # Never forward GitHub credentials to a second hostname.
                async with http.stream("GET", raw_url, headers={"Accept": "text/plain"}) as response:
                    if response.status_code >= 400:
                        raise RepositoryError(f"HTTP {response.status_code}")
                    declared = response.headers.get("content-length", "")
                    if declared.isdigit() and int(declared) > limits.max_file_bytes:
                        raise RepositoryError("raw file exceeds the per-file source limit")
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > limits.max_file_bytes:
                            raise RepositoryError("raw file exceeds the per-file source limit")
                        body.extend(chunk)
            text = bytes(body).decode("utf-8")
            if len(body) > budget:
                raise RepositoryError("raw source exceeds the selected-file byte budget")
            return path, text, len(body)
        except (httpx.HTTPError, UnicodeError, RepositoryError, TimeoutError) as exc:
            errors.append(f"{path}: {type(exc).__name__}")
            return None

    tasks = [asyncio.create_task(fetch(path)) for path, _size in selected]
    try:
        done, pending = await asyncio.wait(tasks, timeout=limits.max_seconds)
    finally:
        # wait() does not cancel children if the HTTP request itself is cancelled.
        unfinished = [task for task in tasks if not task.done()]
        for task in unfinished:
            task.cancel()
        if unfinished:
            await asyncio.gather(*unfinished, return_exceptions=True)
    timed_out_files = len(pending)
    rows = [task.result() for task in done if task.result() is not None]
    bytes_read = sum(row[2] for row in rows)
    if bytes_read > limits.max_bytes:
        # GitHub's own metadata should make this unreachable; still fail closed if
        # a proxy or mock returns inconsistent bodies rather than claiming a bound.
        raise RepositoryError("GitHub raw source exceeded the selected-file byte budget")
    files = {path: content for path, content, _size in sorted(rows)}
    if not files:
        detail = "No supported UTF-8 manifests or source/config files could be read"
        if errors:
            detail += " from GitHub raw content"
        raise RepositoryError(detail)

    failed_files = len(errors) + ignored_metadata_paths + timed_out_files
    complete = not bool(tree.get("truncated")) and not skipped_large and not skipped_budget and not failed_files and len(files) == len(candidates)
    coverage = {
        "mode": "github_tree_selective",
        "archive_downloaded": False,
        "commit_sha": commit,
        "complete": complete,
        "tree_truncated": bool(tree.get("truncated")),
        "repository_files": repository_files,
        "candidate_files": len(candidates),
        "selected_files": len(selected),
        "files_read": len(files),
        "skipped_large_files": skipped_large,
        "skipped_budget_files": skipped_budget,
        "failed_files": failed_files,
        "timed_out_files": timed_out_files,
        "source_read_seconds": round(asyncio.get_running_loop().time() - read_started, 3),
        "time_budget_seconds": limits.max_seconds,
        "per_file_timeout_seconds": limits.per_file_timeout,
        "bytes_read": bytes_read,
        "file_limit": limits.max_files,
        "byte_limit": limits.max_bytes,
        "per_file_limit": limits.max_file_bytes,
        "repository_size_kb": metadata.get("size") if isinstance(metadata.get("size"), int) else None,
    }
    workspace = {
        "id": f"github-{owner}-{repo}", "name": metadata.get("name") or repo,
        "repository": f"{owner}/{repo}", "branch": branch, "environment": "Production",
        "source": "github", "coverage": coverage,
    }
    return workspace, files
