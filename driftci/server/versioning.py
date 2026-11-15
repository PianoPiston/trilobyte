"""Small, deterministic semver/OSV range engine (no package-manager execution)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import total_ordering


@total_ordering
@dataclass(frozen=True)
class Version:
    release: tuple[int, ...]
    prerelease: tuple[int | str, ...] = ()

    @classmethod
    def parse(cls, raw: str) -> "Version":
        value = raw.strip().lstrip("vV")
        value = re.sub(r"^[<>=~^\s]+", "", value)
        value = value.split("+", 1)[0].split(" ", 1)[0]
        match = re.fullmatch(r"(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?", value)
        if not match:
            raise ValueError(f"Unsupported version: {raw!r}")
        release = tuple(int(part) for part in match.group(1).split("."))
        pre = tuple(int(part) if part.isdigit() else part for part in (match.group(2) or "").split(".") if part)
        return cls(release, pre)

    def same_series(self, other: "Version", length: int) -> bool:
        return self.release[:length] == other.release[:length]

    def _release_key(self, other: "Version") -> tuple[tuple[int, ...], tuple[int, ...]]:
        size = max(len(self.release), len(other.release))
        return self.release + (0,) * (size - len(self.release)), other.release + (0,) * (size - len(other.release))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        left, right = self._release_key(other)
        return left == right and self.prerelease == other.prerelease

    def __lt__(self, other: "Version") -> bool:
        left, right = self._release_key(other)
        if left != right:
            return left < right
        if not self.prerelease:
            return False
        if not other.prerelease:
            return True
        return self._pre_key() < other._pre_key()

    def _pre_key(self) -> tuple:
        # Numeric identifiers sort before alphanumeric identifiers in semver.
        return tuple((0, item, "") if isinstance(item, int) else (1, 0, item) for item in self.prerelease)


def _package_matches(affected: dict, name: str, ecosystem: str) -> bool:
    package = affected.get("package") or {}
    return package.get("name") == name and package.get("ecosystem", "").lower() == ecosystem.lower()


def affected_range(affected: dict, name: str, ecosystem: str, raw_version: str) -> bool:
    """Apply OSV introduced/fixed/last_affected semantics to one concrete installed version."""
    if not _package_matches(affected, name, ecosystem):
        return False
    try:
        installed = Version.parse(raw_version)
    except ValueError:
        return False
    if raw_version in (affected.get("versions") or []):
        return True
    for block in affected.get("ranges") or []:
        if block.get("type") not in {"SEMVER", "ECOSYSTEM"}:
            continue
        start = Version.parse("0")
        active = True
        for event in block.get("events") or []:
            try:
                if "introduced" in event:
                    start = Version.parse("0" if event["introduced"] == "0" else event["introduced"])
                    active = True
                elif "fixed" in event:
                    if active and start <= installed < Version.parse(event["fixed"]):
                        return True
                    active = False
                elif "last_affected" in event:
                    if active and start <= installed <= Version.parse(event["last_affected"]):
                        return True
                    active = False
                elif "limit" in event:
                    if active and start <= installed < Version.parse(event["limit"]):
                        return True
                    active = False
            except (ValueError, TypeError):
                active = False
        if active and start <= installed:
            return True
    return False


def advisory_affects(advisory: dict, name: str, ecosystem: str, version: str) -> bool:
    return any(affected_range(item, name, ecosystem, version) for item in advisory.get("affected") or [])


def fixed_version(advisory: dict, name: str, ecosystem: str, version: str) -> str | None:
    """Choose the smallest fixed release, preferring the installed patch/minor series."""
    try:
        installed = Version.parse(version)
    except ValueError:
        return None
    candidates: list[Version] = []
    raw: dict[tuple, str] = {}
    for affected in advisory.get("affected") or []:
        if not _package_matches(affected, name, ecosystem) or not affected_range(affected, name, ecosystem, version):
            continue
        for block in affected.get("ranges") or []:
            for event in block.get("events") or []:
                if "fixed" not in event:
                    continue
                try:
                    candidate = Version.parse(event["fixed"])
                except ValueError:
                    continue
                if candidate > installed:
                    candidates.append(candidate)
                    raw[candidate.release + tuple(map(str, candidate.prerelease))] = event["fixed"]
    if not candidates:
        return None
    for series in (2, 1):
        matching = [candidate for candidate in candidates if candidate.same_series(installed, series)]
        if matching:
            chosen = min(matching)
            return raw[chosen.release + tuple(map(str, chosen.prerelease))]
    chosen = min(candidates)
    return raw[chosen.release + tuple(map(str, chosen.prerelease))]


def cvss3_score(vector: str) -> float | None:
    """Calculate a CVSS 3.x base score; temporal/environmental metrics are deliberately ignored."""
    if not vector.startswith(("CVSS:3.0/", "CVSS:3.1/")):
        return None
    metrics = dict(part.split(":", 1) for part in vector.split("/")[1:] if ":" in part)
    try:
        scope = metrics.get("S", "U")
        av = {"N": .85, "A": .62, "L": .55, "P": .2}[metrics["AV"]]
        ac = {"L": .77, "H": .44}[metrics["AC"]]
        pr_values = {"N": .85, "L": .68 if scope == "C" else .62, "H": .5 if scope == "C" else .27}
        pr = pr_values[metrics["PR"]]
        ui = {"N": .85, "R": .62}[metrics["UI"]]
        cia = [{"N": 0, "L": .22, "H": .56}[metrics[key]] for key in ("C", "I", "A")]
        impact_base = 1 - (1 - cia[0]) * (1 - cia[1]) * (1 - cia[2])
        impact = 6.42 * impact_base if scope == "U" else 7.52 * (impact_base - .029) - 3.25 * (impact_base - .02) ** 15
        if impact <= 0:
            return 0.0
        exploitability = 8.22 * av * ac * pr * ui
        base = min(impact + exploitability, 10) if scope == "U" else min(1.08 * (impact + exploitability), 10)
        return math.ceil((base - 1e-9) * 10) / 10
    except (KeyError, ValueError):
        return None


def advisory_cvss(advisory: dict) -> float | None:
    scores: list[float] = []
    for item in advisory.get("severity") or []:
        raw = str(item.get("score", ""))
        try:
            scores.append(float(raw))
            continue
        except ValueError:
            pass
        score = cvss3_score(raw)
        if score is not None:
            scores.append(score)
    if scores:
        return max(scores)
    try:
        value = (advisory.get("database_specific") or {}).get("cvss", {}).get("score")
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def severity_for(score: float | None, advisory: dict) -> str:
    if score is not None:
        return "critical" if score >= 9 else "high" if score >= 7 else "medium" if score >= 4 else "low" if score > 0 else "info"
    value = str((advisory.get("database_specific") or {}).get("severity", "medium")).lower()
    return value if value in {"critical", "high", "medium", "low"} else "medium"
