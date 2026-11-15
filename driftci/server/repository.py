"""Pinned GitHub metadata, dependency-graph and targeted source reads. No clones or archives."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import time
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import httpx

GITHUB = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?$", re.I)
IGNORED = {".git", "build", "dist", "__pycache__", "coverage"}
MANIFEST_NAMES = {
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "pyproject.toml", "requirements.txt", "requirements.lock", "poetry.lock", "uv.lock", "pipfile.lock",
    "cargo.toml", "cargo.lock", "go.mod", "go.sum", "gemfile", "gemfile.lock",
    "composer.json", "composer.lock", "pubspec.yaml", "pubspec.lock", "build.gradle",
    "build.gradle.kts", "pom.xml", "deps", "version.dat",
    "directory.packages.props", "packages.lock.json", "gradle.lockfile",
}
CODE_SUFFIXES = (
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".json", ".jsonl", ".toml", ".yaml",
    ".ini", ".cfg", ".txt", ".rs", ".go", ".rb", ".php", ".java", ".kt", ".kts", ".swift",
    ".dart", ".scala", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".gradle",
    ".gemspec", ".mod", ".sum", ".lock", ".xml", ".props", ".csproj",
)
NATIVE_HEADERS = {
    "deps/zlib/zlib.h": ("zlib", "ZLIB_VERSION", "z", 16),
    "deps/brotli/c/common/version.h": ("brotli", "BROTLI_VERSION", "uint32_t", 8),
    "deps/openssl/include/openssl/opensslv.h": ("openssl", "OPENSSL_VERSION_STR", "char", 0),
    "deps/cares/include/ares_version.h": ("c-ares", "ARES_VERSION_STR", "char", 0),
    "deps/uv/include/uv/version.h": ("libuv", "UV_VERSION", "", 16),
    "deps/nghttp2/lib/includes/nghttp2/nghttp2ver.h": ("nghttp2", "NGHTTP2_VERSION", "char", 0),
    "deps/ngtcp2/lib/includes/ngtcp2/version.h": ("ngtcp2", "NGTCP2_VERSION", "char", 0),
    "deps/nghttp3/lib/includes/nghttp3/version.h": ("nghttp3", "NGHTTP3_VERSION", "char", 0),
    "deps/llhttp/include/llhttp.h": ("llhttp", "LLHTTP_VERSION_MAJOR", "int", 0),
    "deps/curl/include/curl/curlver.h": ("curl", "LIBCURL_VERSION", "char", 0),
    "deps/histogram/src/hdr_version.h": ("hdr_histogram", "HDR_VERSION", "char", 0),
    "deps/uvwasi/include/uvwasi.h": ("uvwasi", "UVWASI_VERSION_MAJOR", "int", 0),
    "deps/ada/ada.h": ("ada", "ADA_VERSION", "char", 0),
    "deps/simdutf/simdutf.h": ("simdutf", "SIMDUTF_VERSION", "char", 0),
    "deps/simdjson/simdjson.h": ("simdjson", "SIMDJSON_VERSION", "string", 0),
}


class RepositoryError(Exception):
    pass


def parse_github(url: str) -> tuple[str, str]:
    return repository_identity(url)


def safe_relative_path(value: object) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value or len(value) > 1000:
        return None
    path = PurePosixPath(value)
    return path.as_posix() if not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts) else None


@dataclass(frozen=True)
class SourceLimits:
    max_files: int = 1600
    max_bytes: int = 32_000_000
    max_file_bytes: int = 2_000_000
    concurrency: int = 16
    max_seconds: float = 40
    per_file_timeout: float = 12

    def __post_init__(self) -> None:
        if not 1 <= self.max_files <= 8000 or not 100_000 <= self.max_bytes <= 80_000_000:
            raise ValueError("Invalid GitHub metadata/source-reading limits")
        if not 10_000 <= self.max_file_bytes <= 10_000_000 or not 1 <= self.concurrency <= 32:
            raise ValueError("Invalid GitHub file/concurrency limits")
        if not 5 <= self.max_seconds <= 120 or not 1 <= self.per_file_timeout <= 30:
            raise ValueError("Invalid GitHub source-reading deadlines")


def supported_source(path: str) -> bool:
    """Conservative application-source eligibility; manifests like fixtures use a separate inventory path."""
    return is_code_path(path) and not is_test_path(path) and not path.lower().startswith(("node_modules/", "deps/", "vendor/"))


def candidate_priority(path: str) -> tuple:
    """Keep application code ahead of sample apps when source-read capacity is bounded."""
    lowered = path.lower()
    if is_manifest_path(path) and "/" not in path:
        return (0, path)
    if is_test_path(path):
        return (5, path.count("/"), path)
    if any(f"/{part}/" in f"/{lowered}" for part in {"src", "app", "lib", "server", "api", "config", "packages"}):
        return (1, path.count("/"), path)
    if is_manifest_path(path):
        return (3, path.count("/"), path)
    return (4, path.count("/"), path)


def repository_identity(url: str) -> tuple[str, str]:
    """Only canonical public GitHub repository URLs are accepted."""
    if not isinstance(url, str):
        raise RepositoryError("Supply a valid public GitHub repository URL: https://github.com/owner/repository")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.hostname != "github.com" or parsed.port not in (None, 443) or parsed.query or parsed.fragment:
        raise RepositoryError("Use a public repository URL such as https://github.com/owner/repository")
    match = GITHUB.match(url)
    if not match:
        raise RepositoryError("Use a public repository URL such as https://github.com/owner/repository")
    owner, repo = match.groups()
    if repo == ".git":
        raise RepositoryError("Please enter the repository owner and name, not just .git.")
    return owner, repo.removesuffix(".git")


def is_manifest_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1].lower()
    return (
        name in MANIFEST_NAMES or name.startswith("requirements") and name.endswith(".txt")
        or name == "version" and path == "VERSION" or name.endswith((".csproj", ".gemspec", ".lock"))
    )


def is_native_header(path: str) -> bool:
    if path in NATIVE_HEADERS:
        return True
    for known in NATIVE_HEADERS:
        component = "/".join(known.split("/")[:2])
        if path.startswith(component + "/") and path.rsplit("/", 1)[-1] == known.rsplit("/", 1)[-1]:
            return True
    return False


def is_code_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1].lower()
    return path.endswith(CODE_SUFFIXES) or (name.startswith("Dockerfile") and "." not in name[10:]) or path.endswith(".env.example")


def is_test_path(path: str) -> bool:
    """Labels a file's evidence scope. Test fixtures and examples are not silently omitted."""
    lowered = "/" + path.lower().strip("/") + "/"
    return any(part in lowered for part in ("/test/", "/tests/", "/fixtures/", "/fixture/", "/__fixtures__/", "/__tests__/", "/example/", "/examples/", "/demo/", "/docs/", "/documentation/")) or path.lower().endswith((".test.ts", ".test.js", ".spec.ts", ".spec.js"))


def source_scope(path: str) -> str:
    lowered = path.lower()
    if lowered.startswith(("deps/", "third_party/", "node_modules/", "vendor/")) or "/node_modules/" in lowered:
        return "bundled"
    if is_test_path(path):
        return "examples_tests_docs"
    return "application"


class Reader:
    def __init__(self, http: httpx.AsyncClient, owner: str, repo: str, token: str | None, limits: SourceLimits, cache=None, metadata_context=None):
        self.http = http
        self.owner, self.repo, self.limits, self.cache = owner, repo, limits, cache
        self.metadata_context = metadata_context
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.base = f"https://api.github.com/repos/{owner}/{repo}"
        self.remaining: dict = {}
        self.deadline = time.monotonic() + max(0, limits.max_seconds)
        self.cache_writes = 0
        self.context_metadata_reads = 0
        self.context_metadata_error = None

    async def _api_json(self, path: str, byte_limit: int = 50_000_000) -> dict:
        """Read metadata through Context.dev when configured, with a labelled direct fallback."""
        if self.metadata_context is not None:
            result = await self.metadata_context.metadata_json(f"{self.base}{path}", byte_limit)
            if not result.error and isinstance(result.data, dict):
                self.context_metadata_reads += 1
                return result.data
            # A fallback must not erase the failed Context.dev retrieval from coverage.
            self.context_metadata_error = result.error or "Invalid Context.dev metadata response"
        timeout = min(12, max(.05, self.deadline - time.monotonic()))
        try:
            response = await self.http.get(f"{self.base}{path}", headers=self.headers, timeout=timeout, follow_redirects=False)
        except httpx.TimeoutException as exc:
            raise RepositoryError("GitHub metadata or source reads exceeded the repository time budget. Partial reads are reported.") from exc
        if response.status_code == 200:
            if len(response.content) > byte_limit:
                raise RepositoryError("GitHub repository metadata exceeded the declared byte limit")
            try:
                payload = response.json()
            except (ValueError, UnicodeDecodeError) as exc:
                raise RepositoryError("GitHub returned invalid repository metadata") from exc
            if not isinstance(payload, dict):
                raise RepositoryError("GitHub returned invalid repository metadata")
            return payload
        if response.status_code == 404:
            raise RepositoryError("This public repository, branch or commit was not found. Check the URL and whether access is public.")
        if response.status_code in {403, 429}:
            raise RepositoryError("GitHub API rate limit reached or access is restricted. Retry after the reported reset, or configure a least-privilege GitHub token.")
        message = response.json().get("message", "GitHub could not read this public repository") if response.headers.get("content-type", "").startswith("application/json") else "GitHub could not read this public repository"
        raise RepositoryError(f"GitHub API {response.status_code}: {message}")

    async def dependency_graph(self) -> tuple[list[dict], str]:
        """Prefer structured GitHub dependency metadata when available; keep fallback coverage specific."""
        try:
            if self.metadata_context is not None:
                payload = await self._api_json("/dependency-graph/sbom", 12_000_000)
            else:
                response = await self.http.get(f"{self.base}/dependency-graph/sbom", headers=self.headers, params={"per_page": 100}, timeout=min(8, max(.05, self.deadline - time.monotonic())), follow_redirects=False)
                if response.status_code != 200:
                    return [], "HTTP 403: dependency graph unavailable, restricted, or rate-limited; using targeted file parsing" if response.status_code == 403 else f"HTTP {response.status_code}; using targeted file parsing"
                if int(response.headers.get("content-length", "0") or 0) > 12_000_000 or len(response.content) > 12_000_000:
                    return [], "SBOM exceeds the 12 MB metadata limit; using targeted file parsing"
                payload = response.json()
            data = payload.get("sbom", {})
            if not isinstance(data.get("packages"), list):
                raise ValueError("Invalid dependency graph response")
            packages = []
            for package in data.get("packages", [])[:20000]:
                if not isinstance(package, dict):
                    continue
                purl = next((str(ref.get("referenceLocator", "")) for ref in package.get("externalRefs", []) if isinstance(ref, dict) and ref.get("referenceType") == "purl"), "")
                match = re.match(r"^pkg:([^/]+)/(.+?)(?:\?.*)?$", purl)
                if not match:
                    continue
                ecosystem, remainder = match.groups()
                from urllib.parse import unquote
                namespace, _, name_version = remainder.rpartition("/")
                name, at, version = (namespace + "/" + name_version).partition("@") if namespace else name_version.partition("@")
                name = unquote(name).removeprefix("%40")
                version = unquote(version) if at else str(package.get("versionInfo") or "")
                packages.append({"name": name, "version": version if re.match(r"^v?\d+\.\d+", version) else None, "declared_version": version or None, "ecosystem": {"PyPI": "PyPI"}.get(ecosystem, ecosystem), "kind": "library", "scope": "dependency_graph", "certainty": "dependency_graph"})
            return packages, f"GitHub dependency graph: {len(packages)} structured package version(s)"
        except (httpx.HTTPError, ValueError, UnicodeError, AttributeError, RepositoryError) as exc:
            return [], f"HTTP 403: dependency graph unavailable; using targeted file parsing" if self.metadata_context is None and "rate limit" in str(exc).lower() else f" unavailable ({type(exc).__name__}); manifests and native version declarations are used instead"

    def select(self, entries: list[dict]) -> tuple[list[dict], dict]:
        manifest_paths = {entry["path"] for entry in entries if is_manifest_path(entry["path"]) or entry["path"] == "VERSION.dat"}
        manifests = [entry for entry in entries if entry["path"] in manifest_paths]
        native_paths = {entry["path"] for entry in entries if is_native_header(entry["path"])}
        native = [entry for entry in entries if entry["path"] in native_paths]
        code = [entry for entry in entries if is_code_path(entry["path"]) and entry["path"] not in manifest_paths | native_paths and not any(part in IGNORED for part in entry["path"].split("/"))]
        def rank(entry: dict) -> tuple:
            path = entry["path"].lower()
            folder = 0 if path == "package.json" else 1 if path.startswith(("packages/", "apps/", "src/", "lib/")) else 2 if path.startswith("deps/") else 3
            return (is_test_path(path), path.startswith(("node_modules/", "/node_modules/")), folder, path.count("/"), entry.get("size", 0), path)
        ordered = sorted(manifests, key=rank) + sorted(native, key=rank) + sorted(code, key=rank)
        selected, byte_budget, by_kind = [], 0, {"manifest": 0, "native": 0, "code": 0}
        skipped_large = skipped_budget = 0
        for entry in ordered:
            kind = "manifest" if entry in manifests else "native" if entry in native else "code"
            max_file = self.limits.max_file_bytes * 4 if kind == "manifest" else self.limits.max_file_bytes
            size = int(entry.get("size", 0) or 0)
            if size > max_file:
                if kind != "code":
                    skipped_large += 1
                continue
            # Manifests and native declarations reserve their actual consumption only once.
            if len(selected) >= self.limits.max_files:
                skipped_budget += 1
                continue
            if byte_budget + size > self.limits.max_bytes:
                skipped_budget += 1
                continue
            selected.append(dict(entry, kind=kind))
            by_kind[kind] += 1
            byte_budget += size
        manifest_missing = len(manifests) - by_kind["manifest"]
        return selected, {
            "manifest_candidates": len(manifests), "manifest_files_selected": by_kind["manifest"],
            "native_version_files_selected": by_kind["native"],
            "skipped_large_files": skipped_large, "skipped_budget_files": skipped_budget,
            "dependency_manifest_complete": manifest_missing == 0, "dependency_manifest_missing": max(0, manifest_missing),
        }

    def _cached(self, path: str, sha: str) -> str | None:
        if self.cache is None:
            return None
        record = self.cache.cache_get(f"source:{self.owner}/{self.repo}:{self.commit_sha}:{path}")
        body = record.get("body") if record else None
        return body if isinstance(body, str) else None

    async def _raw(self, entry: dict) -> dict:
        path, sha, kind = entry["path"], entry["sha"], entry["kind"]
        limit = self.limits.max_file_bytes * 4 if kind == "manifest" else self.limits.max_file_bytes
        cached = self._cached(path, sha)
        if isinstance(cached, str):
            return {"path": path, "content": cached, "blob_sha": sha, "kind": kind, "scope": source_scope(path), "cached": True}
        timeout = min(self.limits.per_file_timeout, max(.001, self.deadline - time.monotonic()))
        # Raw hosts never receive GitHub Authorization headers or redirects carrying them.
        url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{quote(self.commit_sha, safe='')}/{quote(path, safe='/')}"
        try:
            body = bytearray()
            async with self.http.stream("GET", url, timeout=httpx.Timeout(timeout, read=min(10, timeout))) as response:
                if response.status_code != 200:
                    return {"path": path, "kind": kind, "error": f"Pinned raw source returned HTTP {response.status_code}", "scope": source_scope(path)}
                if int(response.headers.get("content-length", "0") or 0) > limit:
                    return {"path": path, "kind": kind, "error": "Response differs from manifest metadata: per-file budget exceeded", "scope": source_scope(path)}
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > limit:
                        return {"path": path, "kind": kind, "error": "Per-file response-size budget exceeded", "scope": source_scope(path)}
            content = bytes(body).decode("utf-8-sig")
        except (httpx.HTTPError, UnicodeError, ValueError) as exc:
            return {"path": path, "kind": kind, "error": f"{type(exc).__name__}: targeted source read failed", "scope": source_scope(path)}
        if "\x00" in content:
            return {"path": path, "kind": kind, "error": "Binary or unsupported text input was not parsed", "scope": source_scope(path)}
        if self.cache is None or self.cache_sets_remaining <= 0:
            return {"path": path, "content": content, "blob_sha": sha, "kind": kind, "scope": source_scope(path), "cached": False}
        self.cache_sets_remaining -= 1
        digest = hashlib.sha256(content.encode()).hexdigest()
        self.cache.cache_set(f"source:{self.owner}/{self.repo}:{self.commit_sha}:{path}", time.time(), {"body": content, "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "bytes": len(body), "sha256": digest})
        self.cache_writes += 1
        return {"path": path, "content": content, "blob_sha": sha, "kind": kind, "scope": source_scope(path), "cached": False}

    async def read(self, entries: list[dict]) -> tuple[list[dict], dict]:
        started = time.monotonic()
        semaphore = asyncio.Semaphore(max(1, min(32, self.limits.concurrency)))
        self.cache_sets_remaining = 2200
        async def bounded(entry):
            if time.monotonic() >= self.deadline:
                return {"path": entry["path"], "kind": entry["kind"], "error": "Source-read deadline expired before request", "scope": source_scope(entry["path"])}
            async with semaphore:
                return await self._raw(entry)
        tasks = [asyncio.create_task(bounded(entry)) for entry in entries]
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=max(.001, self.deadline - time.monotonic()))
        except (TimeoutError, asyncio.TimeoutError):
            pass
        files = []
        for entry, task in zip(entries, tasks):
            if task.done() and not task.cancelled():
                files.append(task.result())
            else:
                task.cancel()
                files.append({"path": entry["path"], "kind": entry["kind"], "error": "Targeted source-read deadline expired", "scope": source_scope(entry["path"])})
        await asyncio.gather(*tasks, return_exceptions=True)
        selected = {entry["path"]: entry for entry in entries}
        candidate_sizes = sum(int(selected[file["path"]].get("size", 0) or 0) for file in files)
        return files, {"bytes_read": sum(len(file.get("content", "").encode()) for file in files), "candidate_bytes": candidate_sizes, "source_read_seconds": round(time.monotonic() - started, 3)}


async def read_public(http: httpx.AsyncClient, url: str, token: str | None = None, limits: SourceLimits | None = None, cache=None, metadata_context=None) -> tuple[dict, dict[str, str]]:
    """Resolve an immutable commit, read targeted text, and distinguish manifest/read coverage."""
    owner, repo = repository_identity(url)
    reader = Reader(http, owner, repo, token, limits or SourceLimits(), cache, metadata_context)
    repository = await reader._api_json("")
    if repository.get("private"):
        raise RepositoryError("Only public repositories can be connected; credentials are never used to mirror private source.")
    if repository.get("full_name", f"{owner}/{repo}").lower() != f"{owner}/{repo}".lower():
        raise RepositoryError("GitHub repository metadata did not match the requested repository")
    branch = repository.get("default_branch", "main")
    if not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}", branch) or ".." in branch or branch.startswith("-"):
        raise RepositoryError("GitHub returned an unsafe default branch")
    reference = await reader._api_json(f"/git/ref/heads/{quote(branch, safe='')}")
    sha = str((reference.get("object") or {}).get("sha", ""))
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", sha):
        raise RepositoryError("GitHub did not return a valid commit for this repository")
    reader.commit_sha = sha
    tree = await reader._api_json(f"/git/trees/{quote(sha, safe='')}?recursive=1")
    entries = [entry for entry in tree.get("tree", []) if isinstance(entry, dict) and entry.get("type") == "blob" and isinstance(entry.get("path"), str) and isinstance(entry.get("sha"), str)]
    selected, selection = reader.select(entries)
    files, reads = await reader.read(selected)
    graph_packages, graph_status = await reader.dependency_graph()
    manifest_read = [file for file in files if file["kind"] == "manifest"]
    failed_manifests = [file for file in manifest_read if "error" in file]
    eligible_source = {entry["path"] for entry in entries if is_code_path(entry["path"]) or is_manifest_path(entry["path"]) or is_native_header(entry["path"])}
    successful_source = {file["path"] for file in files if "content" in file}
    source_complete = not tree.get("truncated", False) and eligible_source.issubset(successful_source)
    workspace = {
        "id": reader.owner + "/" + repo, "name": f"{owner}/{repo}", "repository": f"{owner}/{repo}",
        "branch": branch, "commit_sha": sha, "environment": "Repository / pinned revision",
        "source": "github", "visibility": "public", "models": [],
        "_structured_packages": graph_packages,
        "coverage": {
            "mode": "targeted_metadata_and_manifests", "complete": not tree.get("truncated", False) and selection["dependency_manifest_complete"] and not failed_manifests,
            "metadata_transport": "context.dev_bytes" if reader.context_metadata_reads else "direct",
            "context_metadata_reads": reader.context_metadata_reads,
            "context_metadata_error": reader.context_metadata_error,
            "source_complete": source_complete,
            "repository_files": len(entries), "candidate_files": len(entries),
            "repository_size_kb": int(repository.get("size", 0) or 0),
            "files_read": len([file for file in files if "content" in file]), "bytes_read": reads["bytes_read"],
            "skipped_large_files": selection["skipped_large_files"], "skipped_budget_files": selection["skipped_budget_files"],
            "failed_files": len([file for file in files if "error" in file]),
            "manifest_candidates": selection["manifest_candidates"], "manifest_files_read": len(manifest_read) - len(failed_manifests),
            "manifest_files_failed": len(failed_manifests), "manifests_missing": selection["dependency_manifest_missing"] + len(failed_manifests),
            "dependency_manifest_complete": selection["dependency_manifest_complete"] and not failed_manifests,
            "native_version_files_read": len([file for file in files if file["kind"] == "native" and "content" in file]),
            "timed_out_files": len([file for file in files if "deadline" in file.get("error", "").lower() or "budget" in file.get("error", "").lower()]),
            "tree_truncated": bool(tree.get("truncated", False)), "commit_sha": sha,
            "source_read_seconds": reads["source_read_seconds"],
            "code_read_is_partial": not source_complete,
            "dependency_graph_status": graph_status, "structured_packages": len(graph_packages),
            "archive_downloaded": False,
            "note": "Complete means every eligible discovered dependency manifest was read, not that every repository source file is indexed. Advisory-query coverage is reported separately. Examples, tests and bundled manifests are labelled, not removed.",
        },
    }
    workspace["_file_records"] = files
    return workspace, {file["path"]: file.get("content", "") for file in files if "content" in file}
