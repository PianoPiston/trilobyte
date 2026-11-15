"""Read-only parsed inventories and source references. Inputs are untrusted text, never programs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import json
import os
from pathlib import Path, PurePosixPath
import re
import tomllib
from collections.abc import Mapping
from xml.etree import ElementTree

CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
CONFIG_SUFFIXES = CODE_SUFFIXES | {".json", ".toml", ".yaml", ".yml", ".h", ".hh", ".hpp", ".hxx", ".c", ".cc", ".cpp", ".cxx", ".go", ".rs", ".java", ".kt", ".swift"}
SOURCE_SUFFIXES = CONFIG_SUFFIXES | {".md", ".txt"}
MANIFEST_NAMES = {"package.json", "package-lock.json", "requirements.txt", "requirements.lock", "pyproject.toml"}
MODEL_RE = re.compile(r"(?<![\w-])((?:gpt-[a-z0-9.-]+|chatgpt-[a-z0-9.-]+|claude-[a-z0-9.-]+|gemini-[a-z0-9.-]+))(?![\w-])", re.I)
SMALL_MODEL_RE = re.compile(r"(?P<quote>['\"`])(?P<model>o[1-9](?:-(?:mini|preview))?(?:-\d{4}-\d{2}-\d{2})?)(?P=quote)", re.I)
MODEL_CONTEXT = re.compile(r"(?:\b[a-z0-9_]*model[a-z0-9_]*|\bmodels)['\"]?\s*[:=(,]+\s*(?:[\[({]\s*)?$", re.I)
EXACT_VERSION = re.compile(r"^v?\d+(?:\.\d+)*(?:[-+][0-9A-Za-z.-]+)?$")


@dataclass(frozen=True)
class Dependency:
    name: str
    ecosystem: str
    version: str
    declared: str
    kind: str
    manifest: str
    exact: bool
    scope: str = "application"
    certainty: str = "declared"
    entry: str = ""

    @property
    def advisory_supported(self) -> bool:
        return self.exact and self.ecosystem not in {"Native", "Project"} and self.certainty not in {"declared", "unresolved"}


def is_test_path(path: str) -> bool:
    """Test paths are labelled rather than silently removed from dependency inventory."""
    parts = PurePosixPath(path).parts
    if any(part.lower() in {"test", "tests", "fixtures", "__fixtures__", "testdata", "test_data", "snapshots", "__snapshots__", "__mocks__", "examples", "demo", "docs"} for part in parts[:-1]):
        return True
    return bool(re.search(r"(?:^|[._-])(?:test|spec)(?:[._-]|$)", parts[-1].lower()))


def snippet_at(content: str, line: int) -> str:
    lines = content.splitlines()
    return lines[line - 1].strip()[:300] if 0 < line <= len(lines) else ""


def comment_only(line: str) -> bool:
    return line.strip().startswith(("//", "#", "/*", "*", "<!--"))


def evidence_for(content: str, path: str, needle: str, reason: str) -> list[dict]:
    return [{"file": path, "line": number, "snippet": line.strip()[:300], "reason": reason} for number, line in enumerate(content.splitlines(), 1) if needle.lower() in line.lower()]


def scope_of(path: str) -> str:
    if path.startswith("::"):
        return "structured_metadata"
    lowered = path.lower()
    if lowered.startswith(("deps/", "vendor/", "third_party/", "node_modules/")) or "/node_modules/" in lowered:
        return "bundled"
    return "examples_tests_docs" if is_test_path(path) else "application"


def _model_identifiers(line: str, lookup: str | None) -> list[tuple[str, str]]:
    """Bare o1/o2-style variable names are not model IDs; require a model-valued assignment."""
    found = []
    for match in MODEL_RE.finditer(line):
        identifier = match.group().rstrip(".-")
        if lookup is None or identifier.lower() == lookup.lower():
            found.append((identifier, "source_identifier" if match.start() == 0 or not MODEL_CONTEXT.search(line[:match.start()]) else "configured_identifier"))
    for match in SMALL_MODEL_RE.finditer(line):
        identifier = match.group("model")
        if lookup is None and not MODEL_CONTEXT.search(line[:match.start()]):
            continue
        if lookup is None or identifier.lower() == lookup.lower():
            found.append((identifier, "source_identifier" if lookup is not None or match.start() == 0 or not MODEL_CONTEXT.search(line[:match.start()]) else "configured_identifier"))
    return found


def model_evidence(files: Mapping, model: str | None = None) -> list[dict]:
    """Find identifiers in narrower application code. Parse separately indexed examples too."""
    result = []
    for path, record in files.items():
        content = record.get("content", record) if isinstance(record, dict) else record
        if not isinstance(content, str):
            continue
        if isinstance(record, dict) and (record.get("error") or record.get("kind") in {"manifest", "native"} or record.get("structured_metadata")):
            continue
        if PurePosixPath(path).name in MANIFEST_NAMES or PurePosixPath(path).suffix not in CONFIG_SUFFIXES:
            continue
        scope = scope_of(path)
        for number, line in enumerate(content.splitlines(), 1):
            if comment_only(line):
                continue
            for identifier, certainty in _model_identifiers(line, model):
                result.append({"file": path, "line": number, "snippet": line.strip()[:300], "reason": "Exact model identifier in selected source; not proof of production invocation", "model": identifier, "scope": scope, "certainty": certainty})
    return result


def production_models(files: Mapping) -> list[str]:
    """Conservative configured-model list: examples/tests/docs/stubs remain labelled evidence."""
    return sorted({item["model"] for item in model_evidence(files) if (item["certainty"] == "configured_identifier" or item["model"].lower().startswith(("gpt-", "claude-", "gemini-", "chatgpt-"))) and not any(part.lower() in {"test", "tests", "fixtures", "__fixtures__", "__snapshots__", "__mocks__", "stub", "stubs", "recordings"} for part in PurePosixPath(item["file"]).parts) and not re.search(r"\.(test|spec)\.", PurePosixPath(item["file"]).name)}, key=str.lower)


def _kind(name: str) -> str:
    if name in {"next", "express", "fastapi", "django", "flask", "svelte"}:
        return "framework"
    if name in {"openai", "anthropic", "@ai-sdk/openai", "@ai-sdk/anthropic", "@anthropic-ai/sdk", "google-generativeai", "@google/generative-ai"}:
        return "ai_sdk"
    if name in {"react", "vue", "svelte", "react-dom"}:
        return "ui"
    return "library"


def _version(value: object) -> tuple[str | None, str | None, bool, str]:
    if not isinstance(value, str):
        return None, None, False, "unresolved"
    declared = value.strip()[:240]
    exact = bool(EXACT_VERSION.fullmatch(declared.removeprefix("=")))
    if declared.startswith(("git+", "github:", "file:", "link:", "workspace:", "portal:")) or re.match(r"^[\w.-]+/[\w.-]+#", declared):
        return None, declared, False, "unresolved"
    return declared.removeprefix("=").removeprefix("v") if exact else None, declared, exact, "locked" if exact else "declared"


def _dep(name: str, ecosystem: str, version: object, declared: object, path: str, entry: str = "", root: bool = False, scope: str | None = None, kind: str | None = None) -> Dependency | None:
    if not isinstance(name, str) or not name.strip() or len(name) > 260:
        return None
    name = name.strip()
    ecosystem = {"pypi": "PyPI", "nuget": "NuGet", "githubactions": "GitHubActions", "crates.io": "crates.io"}.get(ecosystem.lower(), ecosystem)
    resolved, declaration, exact, certainty = _version(version)
    if not declaration and isinstance(declared, str):
        _, declaration, _, _ = _version(declared)
    return Dependency(
        name=name, ecosystem=ecosystem, version=resolved or "", declared=declared or declaration or "",
        kind="project" if root else kind or _kind(name), manifest=path, exact=exact,
        scope=scope or scope_of(path), certainty=certainty, entry=entry[:600],
    )


def _add_package(result: list[Dependency], name: object, eco: str, version: object, declaration: object, path: str, entry: str = "", root: bool = False, kind: str | None = None, scope: str | None = None) -> None:
    if not isinstance(name, str) or not name.strip():
        return
    item = _dep(name, eco, version, declaration, path, entry, root, scope, kind)
    if item is not None:
        result.append(item)


def _json_manifest(data: dict, path: str) -> list[Dependency]:
    result = []
    name = PurePosixPath(path).name.lower()
    if name in {"package.json", "package-lock.json", "npm-shrinkwrap.json", "composer.json"}:
        eco = "Packagist" if name == "composer.json" else "npm"
        bundled_name = re.search(r"(?:^|/)node_modules/((?:@[^/]+/)?[^/]+)/package\.json$", path, re.I)
        package_name = data.get("name") or bundled_name.group(1) if bundled_name else data.get("name")
        bundled = scope_of(path) == "bundled"
        _add_package(result, package_name, eco, data.get("version"), data.get("version"), path, root=not bundled, kind="library" if bundled else None, scope="bundled" if bundled else None)
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            for dep_name, declaration in (data.get(section) or {}).items() if isinstance(data.get(section), dict) else []:
                _add_package(result, dep_name, eco, declaration, declaration, path, entry=section)
        if name != "package.json":
            for entry, item in (data.get("packages") or {}).items() if isinstance(data.get("packages"), dict) else []:
                if not entry or not isinstance(item, dict):
                    continue
                package_name = item.get("name") or entry.rsplit("node_modules/", 1)[-1]
                if entry.endswith("node_modules") or package_name in {"", "node_modules"}:
                    continue
                _add_package(result, package_name, eco, item.get("version"), item.get("version"), path, entry=entry, scope="bundled" if "node_modules/" in entry else None)
            for entry, item in (data.get("dependencies") or {}).items() if isinstance(data.get("dependencies"), dict) else []:
                if isinstance(item, dict):
                    _add_package(result, entry, eco, item.get("version"), item.get("version"), path, entry=f"dependencies/{entry}")
    elif name == "composer.lock":
        for section in ("packages", "packages-dev"):
            for item in data.get(section, []):
                if isinstance(item, dict):
                    _add_package(result, item.get("name"), "Packagist", item.get("version"), item.get("version"), path, entry=section)
    elif name in {"pipfile.lock", "packages.lock.json"}:
        for section in ("default", "develop", "dependencies"):
            for key, item in (data.get(section, {}) or {}).items() if isinstance(data.get(section), dict) else []:
                if isinstance(item, str):
                    _add_package(result, key, "PyPI", item, item, path, entry=section)
                elif isinstance(item, dict):
                    _add_package(result, item.get("name") or key, "PyPI", item.get("version"), item.get("version"), path, entry=section)
    return result


def _toml_manifest(data: dict, path: str, content: str) -> list[Dependency]:
    result = []
    name = PurePosixPath(path).name.lower()
    if name in {"cargo.lock", "uv.lock"}:
        eco = "crates.io" if name == "cargo.lock" else "PyPI"
        for package in data.get("package", []):
            if not isinstance(package, dict):
                continue
            # A local crate's coincidental version is not a registry-version assertion.
            if eco == "crates.io" and not str(package.get("source", "")).startswith("registry+"):
                continue
            if eco == "PyPI" and not package.get("registry") and not package.get("sdist") and not package.get("wheels"):
                continue
            _add_package(result, package.get("name"), eco, package.get("version"), package.get("version"), path, kind="library")
    elif name == "poetry.lock":
        for package in data.get("package", []):
            if isinstance(package, dict):
                _add_package(result, package.get("name"), "PyPI", package.get("version"), package.get("version"), path)
    else:
        project = data.get("project", {})
        _add_package(result, project.get("name"), "PyPI", project.get("version"), project.get("version"), path, root=True)
        for dep in project.get("dependencies", []):
            if isinstance(dep, str):
                match = re.match(r"^\s*([A-Za-z0-9_.-]+)(?:\[[^]]+\])?\s*(.*)", dep)
                if match:
                    declaration = match.group(2).removeprefix("(").removesuffix(")")
                    exact = next((candidate.strip() for candidate in declaration.split("==")[1:] if EXACT_VERSION.fullmatch(candidate.strip())), None)
                    _add_package(result, match.group(1), "PyPI", exact or None, declaration, path)
        poetry = ((data.get("tool") or {}).get("poetry") or {})
        _add_package(result, poetry.get("name"), "PyPI", poetry.get("version"), poetry.get("version"), path, root=True)
        for key, declaration in (poetry.get("dependencies") or {}).items() if isinstance(poetry.get("dependencies"), dict) else []:
            if key.lower() != "python":
                if isinstance(declaration, dict):
                    declaration = declaration.get("version", "")
                _add_package(result, key, "PyPI", declaration, declaration, path)
        for dep_name, declaration in (data.get("dependencies") or {}).items() if name == "cargo.toml" and isinstance(data.get("dependencies"), dict) else []:
            if isinstance(declaration, dict):
                declaration = declaration.get("version", "")
            _add_package(result, dep_name, "crates.io", declaration, declaration, path)
    return result


def _lock_yarn(text: str, path: str) -> list[Dependency]:
    result = []
    if "yarn lockfile v1" in text[:100] or "__metadata:" in text[:160]:
        # The lockfile sel ect or is a range; its indentation-owned version is the resolution.
        selector = None
        for raw in text.splitlines():
            match = re.match(r'^"?((?:@[^/]+/)?[^@,"\s]+)@', raw)
            if raw and not raw.startswith((" ", "\t", "#")) and match:
                selector = match.group(1)
            else:
                version = re.match(r'^\s+(?:version:\s*|version\s+)["\']?([^\s,"\']+)', raw)
                if selector and version:
                    _add_package(result, selector, "npm", version.group(1), version.group(1), path, entry=selector)
                    selector = None
    else:
        package = None
        for raw in text.splitlines():
            if not raw.strip() or raw.startswith("#"):
                continue
            if raw.startswith("  ") and not raw.startswith("    ") and raw.rstrip().endswith(":"):
                package = raw.strip().rstrip(':').strip('"\'')
            elif package and (match := re.match(r'^\s+version:\s*["\']?([^\s,"\']+)', raw)):
                _add_package(result, package, "npm", match.group(1), match.group(1), path, entry=package)
    return result


NATIVE_ALIASES = {
    "brotli": "brotli", "brotli_version": "brotli", "cares": "c-ares", "cares_version": "c-ares",
    "llhttp": "llhttp", "llhttp_version": "llhttp", "nghttp2": "nghttp2", "nghttp2_version": "nghttp2",
    "ngtcp2": "ngtcp2", "ngtcp2_version": "ngtcp2", "nghttp3": "nghttp3", "nghttp3_version": "nghttp3",
    "openssl": "openssl", "openssl_version": "openssl", "zlib": "zlib", "zlib_version": "zlib",
    "libuv": "libuv", "libuv_version": "libuv", "uv": "libuv", "uv_version": "libuv",
    "ada": "ada", "ada_version": "ada", "simdutf": "simdutf", "simdutf_version": "simdutf",
    "simdjson": "simdjson", "simdjson_version": "simdjson", "curl": "curl", "curl_version": "curl",
    "uvwasi": "uvwasi", "uvwasi_version": "uvwasi", "hdr_histogram": "hdr_histogram", "hdr_histogram_version": "hdr_histogram",
    "sqlite": "sqlite", "sqlite_version": "sqlite", "v8": "v8", "v8_version": "v8",
    "acorn": "acorn", "acorn_version": "acorn", "undici": "undici", "undici_version": "undici",
    "icu": "icu", "icu_version": "icu", "small-icu": "icu", "nbytes": "nbytes", "nbytes_version": "nbytes",
}


def _native_value(component: str, macro: str, value: str) -> str | None:
    value = value.strip().strip('"\'').removeprefix('"').removeprefix("0x")
    if macro.endswith(("_MAJOR", "_MINOR", "_PATCH", "_RELEASE")):
        return None
    if "[" in value:
        return ".".join(__import__("re").findall(r"\d+", value)[:3])
    if re.fullmatch(r"[0-9A-Fa-f]+", value):
        number = int(value, 16)
        if macro in {"ZLIB_VERSION", "BROTLI_VERSION", "UV_VERSION"}:
            return f"{(number >> 16) & 255}.{(number >> 8) & 255}.{number & 255}"
    match = re.search(r"(?<![\d.])v?(\d+\.\d+(?:\.\d+)*(?:-[0-9A-Za-z.-]+)?)", value)
    return match.group(1) if match else None


def native_versions(path: str, content: str) -> list[Dependency]:
    """Parse explicit version declarations only; never compile or calculate C/C++ expressions."""
    result = []
    found: set[str] = set()
    macros = re.findall(r"^\s*#\s*define\s+([A-Za-z0-9_]+)\s+[^\n]*?([\"']?)([0-9v][^\"'\n/]*)\2", content, re.M)
    by_macro = {name: value.strip() for name, _quote, value in macros if re.match(r"^[A-Z0-9_]*VERSION(?:_[A-Z0-9_]+)*$", name)}
    for component in set(NATIVE_ALIASES.values()):
        prefix = {"c-ares": "ARES", "libuv": "UV", "curl": "LIBCURL", "brotli": "BROTLI"}.get(component, component.upper().replace("-", "_"))
        string_key = next((key for key in (f"{prefix}_VERSION_STR", f"{prefix}_VERSION_STRING", f"{prefix}_VERSION_TEXT", f"{prefix}_VERSION", f"{component}_VERSION") if key in by_macro), None)
        if string_key:
            for value in re.findall(r'^\s*#\s*define\s+' + string_key + r'\s+([^/\n]+)', content, re.M):
                version = _native_value(component, string_key, value)
                if version:
                    _add_package(result, component, "Native", version, version, path, entry=string_key, kind="native")
                    found.add(component)
                    break
        if component in found:
            continue
        major = next((key for key in (f"{prefix}_MAJOR", f"{prefix}_VERSION_MAJOR", f"{component}_VERSION_MAJOR") if key in by_macro), None)
        if major:
            values = []
            for part in ("MAJOR", "MINOR", "PATCH"):
                key = re.sub("MAJOR$", part, major)
                value = by_macro.get(key, "")
                values.append(value if value.isdigit() else "0")
            if all(values):
                version = ".".join(values)
                _add_package(result, component, "Native", version, version, path, entry=major, kind="native")
                found.add(component)
    lowered = path.lower()
    if lowered.endswith(("/deps", "version.dat")) or lowered in {"deps", "version.dat"}:
        for name, value in re.findall(r"(?m)^\s*['\"]?([A-Za-z0-9_.-]+)['\"]?\s*:\s*(?:DString\(\s*)?['\"]([0-9][^'\"\n]*)['\"]", content):
            component = NATIVE_ALIASES.get(name.lower())
            version = _native_value(component or "", "", value) if component else None
            if component and component not in found and version:
                _add_package(result, component, mingleco(component), version, value, path, entry=name, kind="library" if mingleco(component) != "Native" else "native")
                found.add(component)
    return result


def mingleco(name: str) -> str:
    return "npm" if name in {"acorn", "undici"} else "crates.io" if name == "nbytes" else "Native"


def _lines_manifest(path: str, content: str) -> list[Dependency]:
    result = []
    name = PurePosixPath(path).name.lower()
    eco = {"go.mod": "Go", "go.sum": "Go", "gemfile.lock": "RubyGems", "gemfile": "RubyGems", "pubspec.lock": "Pub", "pubspec.yaml": "Pub"}.get(name, "PyPI")
    if name.startswith("requirements"):
        for raw in content.splitlines():
            line = raw.split("#", 1)[0].split(";", 1)[0].strip()
            if match := re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?\s*(.*)", line):
                exact = re.search(r"==\s*([0-9][\w.+!-]*)", match.group(2))
                _add_package(result, match.group(1), "PyPI", exact.group(1) if exact else None, match.group(2), path)
    elif name == "go.mod":
        in_block = False
        for raw in content.splitlines():
            line = raw.split("//", 1)[0].strip()
            if line.startswith("require ("):
                in_block = True
            elif in_block and line == ")":
                in_block = False
            else:
                match = re.match(r"(?:require\s+)?([\w.~/-]+)\s+v([\w.+-]+)", line)
                if match and (in_block or line.startswith("require ")):
                    _add_package(result, match.group(1), "Go", match.group(2), "v" + match.group(2), path)
    elif name == "go.sum":
        for line in content.splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[1].startswith("v") and not parts[1].endswith("/go.mod"):
                _add_package(result, parts[0], "Go", parts[1][1:], parts[1], path)
    elif name == "pubspec.lock":
        package = None
        for line in content.splitlines():
            if match := re.match(r"^  ([\w-]+):\s*$", line):
                package = match.group(1)
            elif package and (match := re.match(r'^\s+version:\s*["\']?([^\s"\']+)', line)):
                _add_package(result, package, "Pub", match.group(1), match.group(1), path, entry=package)
                package = None
    elif name in {"gemfile.lock", "pubspec.yaml"}:
        matches = re.findall(r"^    ([A-Za-z0-9_-]+) \(([^)]+)\)", content, re.M) if name == "gemfile.lock" else re.findall(r"^  ([A-Za-z0-9_-]+):\s*([^\s#]+)", content, re.M)
        for package, version in matches:
            _add_package(result, package, eco, version, version, path)
    elif name == "gemfile":
        for package, version in re.findall(r"^\s*gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+))?", content, re.M):
            _add_package(result, package, "RubyGems", version, version, path)
    elif name.endswith(".gemspec"):
        package = re.search(r"(?:name|gem_specification\.name)\s*=\s*['\"]([^'\"]+)", content)
        version = re.search(r"\.version\s*=\s*['\"]([^'\"]+)", content)
        if package and version:
            _add_package(result, package.group(1), "RubyGems", version.group(1), version.group(1), path)
    elif name in {"build.gradle", "build.gradle.kts"}:
        variables = {}
        for package, version in re.findall(r"(?:\w+[Vv]ersion|[Vv]ersion)[=\"' \t]+([0-9][\w.+-]*)", content):
            variables[package] = version
        for dep, version in re.findall(r'[\w.:-]+\s+["\']([\w.-]+:[\w.-]+):([\w.+-]+|[$][^"\']+)["\']', content):
            variables.setdefault(dep, version)
        for dep, version in variables.items():
            _add_package(result, dep, "Maven", version, version, path)
    elif name == "gradle.lockfile":
        for line in content.splitlines():
            parts = line.split(":")
            if len(parts) == 3:
                _add_package(result, parts[0] + ":" + parts[1], "Maven", parts[2].split("=")[0], parts[2], path)
    return result


def _xml_manifest(path: str, content: str) -> list[Dependency]:
    if "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper():
        raise ValueError("DTD/entity XML is rejected")
    root = ElementTree.fromstring(content)
    tag = lambda element: element.tag.rsplit("}", 1)[-1]
    def children(element, name):
        return [child for child in element if tag(child) == name]
    def text(element, name, default=""):
        child = next(iter(children(element, name)), None)
        return child.text.strip() if child is not None and child.text else default
    result = []
    if PurePosixPath(path).name == "pom.xml":
        props = next(iter(children(root, "properties")), None)
        properties = {tag(item): (item.text or "").strip() for item in props} if props is not None else {}
        for dependencies in children(root, "dependencies"):
            for dependency in children(dependencies, "dependency"):
                group, artifact, version = text(dependency, "groupId"), text(dependency, "artifactId"), text(dependency, "version")
                version = properties.get(version.removeprefix("${").removesuffix("}"), version)
                _add_package(result, group + ":" + artifact, "Maven", version, version, path)
    elif PurePosixPath(path).name.lower() == "directory.packages.props":
        for element in root.iter():
            if tag(element) == "PackageVersion":
                _add_package(result, element.attrib.get("Include"), "NuGet", element.attrib.get("Version"), element.attrib.get("Version"), path)
    else:
        for element in root.iter():
            if tag(element) == "PackageReference":
                version = element.attrib.get("Version") or text(element, "Version")
                _add_package(result, element.attrib.get("Include"), "NuGet", version, version, path)
    return result


def read_manifest(record: dict, path: str) -> list[Dependency]:
    """Parse formats explicitly, preserving ranges and evidence scopes without executing package code."""
    content = record.get("content", "")
    if record.get("structured_metadata"):
        return [_dep(str(item["name"]), item["ecosystem"], item.get("version"), item.get("declared_version") or item.get("version"), path, scope="dependency_graph", kind=item.get("kind")) for item in record.get("manifest", {}).get("packages", []) if item.get("name")]
    if not content or record.get("error"):
        return []
    if record.get("kind") == "native" or PurePosixPath(path).name.lower() in {"deps", "version.dat"}:
        return native_versions(path, content)
    name = PurePosixPath(path).name.lower()
    if name.endswith(".json") or name in {"npm-shrinkwrap.json", "package-lock.json", "composer.lock", "pipfile.lock"}:
        return _json_manifest(json.loads(content), path)
    if name.endswith(".toml") or name in {"poetry.lock", "cargo.lock", "uv.lock"}:
        return _toml_manifest(tomllib.loads(content), path, content)
    if name in {"yarn.lock", "pnpm-lock.yaml"}:
        return _lock_yarn(content, path)
    if name.endswith(".xml") or name.endswith(".csproj") or name.endswith(".props"):
        return _xml_manifest(path, content)
    return _lines_manifest(path, content)


def usage_index(files: Mapping, packages: set[tuple[str, str]]) -> dict[tuple[str, str], int]:
    """Index imports once per file instead of searching every file separately for every package."""
    npm_names = {name.lower() for eco, name in packages if eco == "npm"}
    python_names = {name.lower().replace("-", "_"): name for eco, name in packages if eco == "PyPI"}
    other_names = {(eco, name.lower()): name for eco, name in packages if eco not in {"npm", "PyPI", "Native", "Project"} and len(name) >= 4}
    other_ecosystems = {eco for eco, _name in other_names}
    result: dict[tuple[str, str], int] = {}
    npm_import = re.compile(r"(?:\bfrom\s*|\bimport\s*(?:\(\s*)?|\brequire(?:\.resolve)?\s*\(\s*)['\"]([^'\"]+)['\"]")
    python_import = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", re.MULTILINE)
    token = re.compile(r"(?<![\w@-])[@+\w.-]+(?:/[@+\w.-]+)?(?![\w-])")

    def count(ecosystem: str, name: str) -> None:
        key = (ecosystem, name)
        result[key] = result.get(key, 0) + 1

    for path, record in files.items():
        content = record.get("content", record) if isinstance(record, dict) else record
        if not isinstance(content, str) or PurePosixPath(path).name in MANIFEST_NAMES or (isinstance(record, dict) and record.get("kind") in {"manifest", "native"}):
            continue
        npm_referenced, python_referenced, other_referenced = set(), set(), set()
        for match in token.finditer(content):
            value = match.group().lower()
            for eco in other_ecosystems:
                original = other_names.get((eco, value))
                if original is not None:
                    other_referenced.add((eco, original))
        code = "\n".join(line for line in content.splitlines() if not comment_only(line))
        for module in npm_import.findall(code):
            parts = module.lower().split("/")
            name = "/".join(parts[:2]) if parts and parts[0].startswith("@") else parts[0]
            if name in npm_names:
                npm_referenced.add(name)
        for match in python_import.finditer(code):
            name = match.group(1).lower().split(".", 1)[0]
            if name in python_names:
                python_referenced.add(python_names[name])
        for eco, name in other_referenced:
            count(eco, name)
        for name in npm_referenced:
            count("npm", name)
        for name in python_referenced:
            count("PyPI", name)
    return result


def package_usage(files: Mapping, name: str, ecosystem: str) -> int:
    return usage_index(files, {(ecosystem, name)}).get((ecosystem, name), 0)


def middleware_evidence(files: Mapping) -> list[dict]:
    for path in sorted(files):
        if PurePosixPath(path).name not in {"middleware.ts", "middleware.js"}:
            continue
        record = files[path]
        content = record.get("content", record) if isinstance(record, dict) else record
        for number, line in enumerate(content.splitlines(), 1):
            if not comment_only(line) and re.search(r"auth|token|session|cookie|jwt", line, re.I):
                return [{"file": path, "line": number, "snippet": line.strip()[:300], "reason": "Authorization-related middleware; reachability is a heuristic, not proof of exploitability"}]
    return []


def dependency_evidence(files: Mapping, dependency: Dependency) -> list[dict]:
    if dependency.manifest.startswith("::"):
        return [{"file": "GitHub dependency graph", "line": 1, "snippet": f"{dependency.ecosystem} package {dependency.name}@{dependency.version}", "reason": "Structured dependency-graph metadata; independently verify the declared SBOM mapping"}]
    record = files.get(dependency.manifest, {})
    content = record.get("content", record) if isinstance(record, dict) else record
    needle = dependency.entry if dependency.kind == "native" and dependency.entry else dependency.name
    reason = "Explicit native/bundled version declaration; not proof of platform vulnerability" if dependency.ecosystem == "Native" else "Installed or declared dependency"
    evidence = evidence_for(content, dependency.manifest, needle, reason)
    if dependency.ecosystem == "npm" and dependency.name == "next":
        evidence.extend(middleware_evidence(files))
    return evidence[:12]


def parse_inventory(files: Mapping) -> tuple[list[Dependency], list[dict]]:
    packages, errors = [], []
    structured = any(isinstance(record, dict) for record in files.values())
    for path, record in sorted(files.items()):
        if not isinstance(record, dict):
            if structured:
                continue
            name = PurePosixPath(path).name.lower()
            if name not in MANIFEST_NAMES and not name.endswith(".lock"):
                continue
            record = {"content": record, "kind": "manifest"}
        if record.get("kind") not in {"manifest", "native"} and not record.get("structured_metadata"):
            continue
        before = len(packages)
        try:
            packages.extend(read_manifest(record, path))
        except (ValueError, TypeError, AttributeError, ElementTree.ParseError, tomllib.TOMLDecodeError) as exc:
            errors.append({"path": path, "reason": f"Manifest could not be parsed: {type(exc).__name__}"})
        if any(item.ecosystem == "Native" for item in packages[before:]):
            packages[before:] = [Dependency(**{**asdict(item), "scope": "examples_tests_docs" if scope_of(path) == "examples_tests_docs" else "bundled", "certainty": "native_declaration"}) if item.ecosystem == "Native" else item for item in packages[before:]]
    unique = {}
    for item in packages:
        if item.ecosystem == "PyPI":
            item = Dependency(**{**asdict(item), "name": item.name.lower().replace("_", "-")})
        # Prefer an exact registry-lock resolution over a manifest range at the same source.
        key = (item.ecosystem.lower(), item.name.lower(), item.version.lower(), str(PurePosixPath(item.manifest).parent))
        old = unique.get(key)
        if old is None or item.exact and not old.exact or old.scope == "bundled" and item.scope != "bundled" or item.certainty == "dependency_graph":
            unique[key] = item
    return list(unique.values()), errors


def advisory_versions(files: Mapping) -> list[Dependency]:
    """Exclude the application's own project version and unsupported declaration-only comparisons."""
    dependencies, _errors = parse_inventory(files)
    return [item for item in dependencies if item.kind != "project" and item.ecosystem != "Native"]


def _inventory_snapshot_key(files: Mapping) -> tuple:
    rows = []
    for path, value in sorted(files.items()):
        if isinstance(value, dict):
            metadata = {key: item for key, item in value.items() if key not in {"content", "cached", "blob_sha"}}
            rows.append((path, value.get("content", ""), json.dumps(metadata, sort_keys=True)))
        else:
            rows.append((path, value, ""))
    return tuple(rows)


@lru_cache(maxsize=2)
def _snapshot_inventory(snapshot: tuple) -> tuple:
    files = {path: {"content": content, **json.loads(metadata)} if metadata else content for path, content, metadata in snapshot}
    return tuple(_compute_inventory(files))


def inventory(files: Mapping, issues: Mapping[tuple[str, str], int] | None = None) -> list[dict]:
    """Inventory an immutable snapshot; repeated phases share its expensive parse."""
    result = []
    for row in _snapshot_inventory(_inventory_snapshot_key(files)):
        data = dict(row)
        if issues:
            count = sum(number for (ecosystem, name), number in issues.items() if ecosystem.lower() == data["ecosystem"].lower() and name.lower() == data["name"].lower())
            data.update(issues=count, health="critical" if count else data["health"])
        result.append(data)
    return result


def _compute_inventory(files: Mapping) -> list[dict]:
    dependencies, parse_errors = parse_inventory(files)
    dependencies = [item for item in dependencies if item.kind != "project"]
    usages = usage_index(files, {(item.ecosystem, item.name) for item in dependencies})
    result = []
    for item in sorted(dependencies, key=lambda value: (value.name.lower(), value.ecosystem, value.manifest)):
        data = asdict(item)
        data["resolved_version"] = item.version or None
        data["version"] = item.version if item.exact else item.declared or "unresolved"
        data.update({
            "usage_count": usages.get((item.ecosystem, item.name.lower()), usages.get((item.ecosystem, item.name), 0)),
            "issues": 0,
            "health": "unresolved" if item.ecosystem == "Native" or not item.exact else "healthy",
            "advisory_supported": item.advisory_supported,
        })
        result.append(data)
    return result


def read_text_tree(root: Path) -> dict[str, str]:
    """Read bounded local examples without following external symlinks or importing anything."""
    if not root.is_dir():
        return {}
    try:
        base = root.resolve(strict=True)
    except OSError:
        return {}
    result, total = {}, 0
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
                result[resolved.relative_to(base).as_posix()] = resolved.read_text(encoding="utf-8")
                total += size
            except (OSError, UnicodeError):
                continue
    return result
