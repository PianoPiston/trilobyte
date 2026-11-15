"""Read-only repository inventory. Repository text is never imported, evaluated or executed."""
from __future__ import annotations

import json
import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
CONFIG_SUFFIXES = CODE_SUFFIXES | {".json", ".toml", ".yaml", ".yml"}
SOURCE_SUFFIXES = CONFIG_SUFFIXES | {".md", ".txt"}
MANIFEST_NAMES = {"package.json", "package-lock.json", "requirements.txt", "requirements.lock", "pyproject.toml"}
MODEL_RE = re.compile(r"(?<![\w-])((?:gpt-[a-z0-9.-]+|o[1-9](?:-mini|-preview)?|chatgpt-[a-z0-9.-]+|claude-[a-z0-9.-]+|gemini-[a-z0-9.-]+))(?![\w-])", re.I)


@dataclass(frozen=True)
class Dependency:
    name: str
    ecosystem: str
    version: str
    declared: str
    kind: str
    manifest: str
    exact: bool


def snippet_at(content: str, line: int) -> str:
    lines = content.splitlines()
    return lines[line - 1].strip()[:300] if 0 < line <= len(lines) else ""


def comment_only(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("//", "#", "/*", "*", "<!--"))


def evidence_for(content: str, path: str, needle: str, reason: str) -> list[dict]:
    result = []
    for number, line in enumerate(content.splitlines(), 1):
        if needle.lower() in line.lower():
            result.append({"file": path, "line": number, "snippet": line.strip()[:300], "reason": reason})
    return result


def model_evidence(files: Mapping[str, str], model: str | None = None) -> list[dict]:
    """Find configured model IDs in code/config, never documentation."""
    result = []
    for path, content in sorted(files.items()):
        if PurePosixPath(path).name in MANIFEST_NAMES or PurePosixPath(path).suffix not in CONFIG_SUFFIXES:
            continue
        for number, line in enumerate(content.splitlines(), 1):
            if comment_only(line):
                continue
            matches = MODEL_RE.findall(line)
            for match in matches:
                match = match.rstrip(".-")
                if model is None or match.lower() == model.lower():
                    result.append({"file": path, "line": number, "snippet": line.strip()[:300], "reason": "Exact configured model identifier", "model": match})
    return result


def production_models(files: Mapping[str, str]) -> list[str]:
    return sorted({item["model"] for item in model_evidence(files)}, key=str.lower)


def _kind(name: str) -> str:
    if name in {"next", "express", "fastapi", "django", "flask", "svelte"}:
        return "framework"
    if name in {"openai", "anthropic", "@anthropic-ai/sdk", "google-generativeai", "@google/generative-ai"}:
        return "ai_sdk"
    if name in {"react", "vue", "svelte", "react-dom"}:
        return "ui"
    return "library"


def _lock_npm(content: str) -> tuple[dict[str, str], dict]:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return {}, {}
    if not isinstance(data, dict):
        return {}, {}
    versions: dict[str, str] = {}
    packages = data.get("packages") or {}
    if isinstance(packages, dict):
        for path, item in packages.items():
            if not path.startswith("node_modules/") or not isinstance(item, dict):
                continue
            name = path.rsplit("node_modules/", 1)[-1]
            if isinstance(item.get("version"), str):
                versions[name] = item["version"]

    def visit(items: object) -> None:
        if not isinstance(items, dict):
            return
        for name, item in items.items():
            if isinstance(item, dict) and isinstance(item.get("version"), str):
                versions.setdefault(name, item["version"])

    visit(data.get("dependencies"))
    return versions, data


def _npm_inventory(files: Mapping[str, str]) -> list[Dependency]:
    result = []
    for manifest_path, content in sorted(files.items()):
        if PurePosixPath(manifest_path).name != "package.json":
            continue
        try:
            manifest = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(manifest, dict):
            continue
        parent = PurePosixPath(manifest_path).parent.as_posix()
        lock_path = "package-lock.json" if parent == "." else f"{parent}/package-lock.json"
        locked, _ = _lock_npm(files.get(lock_path, ""))
        declarations: dict[str, str] = {}
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            values = manifest.get(section) or {}
            if isinstance(values, dict):
                for name, spec in values.items():
                    if isinstance(spec, str):
                        declarations.setdefault(name, spec)
        for name, spec in declarations.items():
            pinned = bool(re.fullmatch(r"\d+(?:\.\d+)*(?:-[0-9A-Za-z.-]+)?", spec.strip()))
            version = locked.get(name, spec)
            if version:
                result.append(Dependency(name, "npm", version, spec, _kind(name), manifest_path, name in locked or pinned))
    return result


def _python_inventory(files: Mapping[str, str]) -> list[Dependency]:
    records: dict[tuple[str, str], Dependency] = {}
    requirement = re.compile(r"^([A-Za-z0-9_.-]+)\s*(?:\[[^]]+\])?\s*(==|>=|<=|~=|!=|>|<)\s*([A-Za-z0-9.*+!_-]+)")
    for path, content in sorted(files.items()):
        if PurePosixPath(path).name not in {"requirements.txt", "requirements.lock"}:
            continue
        for raw in content.splitlines():
            line = raw.split("#", 1)[0].split(";", 1)[0].strip()
            match = requirement.match(line)
            if not match or match.group(2) != "==":
                continue
            normalized = match.group(1).lower().replace("_", "-")
            records[(normalized, path)] = Dependency(normalized, "PyPI", match.group(3), match.group(0), _kind(normalized), path, "*" not in match.group(3))
    for project_path, content in sorted(files.items()):
        if PurePosixPath(project_path).name != "pyproject.toml":
            continue
        try:
            project = tomllib.loads(content)
        except tomllib.TOMLDecodeError:
            continue
        dependencies = (project.get("project") or {}).get("dependencies") or []
        for value in dependencies:
            if not isinstance(value, str):
                continue
            match = requirement.match(value.strip())
            if match and match.group(2) == "==":
                normalized = match.group(1).lower().replace("_", "-")
                records[(normalized, project_path)] = Dependency(normalized, "PyPI", match.group(3), value, _kind(normalized), project_path, "*" not in match.group(3))
        poetry = ((project.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
        if isinstance(poetry, dict):
            for name, spec in poetry.items():
                if name.lower() == "python" or not isinstance(spec, str):
                    continue
                if re.fullmatch(r"\d+(?:\.\d+)*(?:-[0-9A-Za-z.-]+)?", spec):
                    normalized = name.lower().replace("_", "-")
                    records[(normalized, project_path)] = Dependency(normalized, "PyPI", spec, spec, _kind(normalized), project_path, True)
    return list(records.values())


def usage_index(files: Mapping[str, str], packages: set[tuple[str, str]]) -> dict[tuple[str, str], int]:
    """Extract configured imports in one source pass, not one pass per dependency."""
    npm_names = {name for ecosystem, name in packages if ecosystem == "npm"}
    python_names = {name for ecosystem, name in packages if ecosystem == "PyPI"}
    result: dict[tuple[str, str], int] = {}
    npm_import = re.compile(r"(?:\bfrom\s*|\bimport\s*(?:\(\s*)?|\brequire(?:\.resolve)?\s*\(\s*)['\"]([^'\"]+)['\"]")
    python_import = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)")
    for path, content in files.items():
        if PurePosixPath(path).name in MANIFEST_NAMES or PurePosixPath(path).suffix not in CONFIG_SUFFIXES:
            continue
        npm_referenced: set[str] = set()
        python_referenced: set[str] = set()
        for line in content.splitlines():
            if comment_only(line):
                continue
            for module in npm_import.findall(line):
                for name in npm_names:
                    if module == name or module.startswith(name + "/"):
                        npm_referenced.add(name)
            match = python_import.match(line)
            if match:
                module = match.group(1)
                for name in python_names:
                    target = name.replace("-", "_")
                    if module == target or module.startswith(target + "."):
                        python_referenced.add(name)
        for name in npm_referenced:
            result[("npm", name)] = result.get(("npm", name), 0) + 1
        for name in python_referenced:
            result[("PyPI", name)] = result.get(("PyPI", name), 0) + 1
    return result


def package_usage(files: Mapping[str, str], name: str, ecosystem: str) -> int:
    """Compatibility helper for single-package callers; inventory uses one shared pass."""
    return usage_index(files, {(ecosystem, name)}).get((ecosystem, name), 0)


def middleware_evidence(files: Mapping[str, str]) -> list[dict]:
    preferred = ("middleware.ts", "middleware.js", "src/middleware.ts", "src/middleware.js")
    candidates = [path for path in preferred if path in files]
    candidates.extend(sorted(path for path in files if path not in preferred and PurePosixPath(path).name in {"middleware.ts", "middleware.js"}))
    for path in candidates:
        if path not in files:
            continue
        content = files[path]
        for number, line in enumerate(content.splitlines(), 1):
            if not comment_only(line) and re.search(r"auth|token|session|cookie|jwt", line, re.I):
                return [{"file": path, "line": number, "snippet": line.strip()[:300], "reason": "Authorization-related middleware; reachability is a heuristic, not proof of exploitability"}]
        return [{"file": path, "line": 1, "snippet": snippet_at(content, 1), "reason": "Next.js middleware present; verify deployment behavior"}]
    return []


def dependency_evidence(files: Mapping[str, str], dependency: Dependency) -> list[dict]:
    evidence = evidence_for(files.get(dependency.manifest, ""), dependency.manifest, f'"{dependency.name}"' if dependency.ecosystem == "npm" else dependency.name, "Installed dependency declaration")
    if dependency.ecosystem == "npm" and dependency.name == "next":
        evidence.extend(middleware_evidence(files))
    return evidence[:12]


def inventory(files: Mapping[str, str], issues: Mapping[tuple[str, str], int] | None = None) -> list[dict]:
    dependencies = {(item.ecosystem, item.name, item.manifest): item for item in _npm_inventory(files) + _python_inventory(files)}
    usages = usage_index(files, {(ecosystem, name) for ecosystem, name, _manifest in dependencies})
    issues = issues or {}
    result = []
    for (ecosystem, name, _manifest), item in sorted(dependencies.items(), key=lambda pair: (pair[0][1], pair[0][0], pair[0][2])):
        count = issues.get((ecosystem, name), 0)
        data = asdict(item)
        data.update({
            "usage_count": usages.get((ecosystem, name), 0),
            "issues": count,
            "health": "critical" if count else "healthy" if item.exact else "unresolved",
        })
        result.append(data)
    return result


def read_text_tree(root: Path) -> dict[str, str]:
    """Read a bounded source tree without following external symlinks or executing anything."""
    if not root.is_dir():
        return {}
    try:
        base = root.resolve(strict=True)
    except OSError:
        return {}
    result: dict[str, str] = {}
    total = 0
    ignored = {".git", "node_modules", "dist", ".next", "venv", ".venv", "__pycache__"}
    for directory, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name not in ignored)
        for filename in sorted(filenames):
            path = Path(directory, filename)
            if PurePosixPath(filename).suffix not in SOURCE_SUFFIXES:
                continue
            try:
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(base) or not resolved.is_file():
                    continue
                size = resolved.stat().st_size
                if size > 1_000_000 or total + size > 20_000_000 or len(result) >= 2000:
                    continue
                content = resolved.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            result[resolved.relative_to(base).as_posix()] = content
            total += size
    return result
