"""Live OSV and CISA KEV clients plus deterministic advisory normalization."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .db import Database
from .scanner import Dependency
from .util import safe_excerpt
from .versioning import advisory_affects, advisory_cvss, severity_for
from .web import CachedWebClient, WebResult

OSV_QUERY = "https://api.osv.dev/v1/query"
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


@dataclass
class PackageIntel:
    dependency: Dependency
    advisories: list[dict]
    result: WebResult


def cve_id(advisory: dict) -> str | None:
    identifiers = [advisory.get("id", "")] + list(advisory.get("aliases") or []) + list(advisory.get("_ids") or [])
    return sorted({item for item in identifiers if isinstance(item, str) and item.startswith("CVE-")})[0] if any(isinstance(item, str) and item.startswith("CVE-") for item in identifiers) else None


def deduplicate(advisories: list[dict]) -> list[dict]:
    """Merge OSV records joined by CVE/GHSA aliases, including transitive aliases."""
    valid = [item for item in advisories if isinstance(item, dict) and isinstance(item.get("id"), str)]
    parent = list(range(len(valid)))
    owners: dict[str, int] = {}

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left, right = root(left), root(right)
        if left != right:
            parent[right] = left

    for index, advisory in enumerate(valid):
        for ident in [advisory["id"]] + list(advisory.get("aliases") or []):
            if not isinstance(ident, str):
                continue
            if ident in owners:
                union(index, owners[ident])
            else:
                owners[ident] = index
    groups: dict[int, list[dict]] = {}
    for index, advisory in enumerate(valid):
        groups.setdefault(root(index), []).append(advisory)

    def quality(item: dict) -> tuple:
        return (bool(item.get("affected")), bool(item.get("summary")), bool(item.get("severity")), len(item.get("references") or []), item.get("id", "").startswith("GHSA-"))

    merged = []
    for group in groups.values():
        best = deepcopy(max(group, key=quality))
        identifiers = sorted({ident for item in group for ident in [item.get("id")] + list(item.get("aliases") or []) if isinstance(ident, str)})
        best["_ids"] = identifiers
        best["aliases"] = [ident for ident in identifiers if ident != best.get("id")]
        # Prefer whichever record currently has the richest affected ranges for fixed-version calculations.
        richest = max(group, key=lambda item: len(item.get("affected") or []))
        best["affected"] = deepcopy(richest.get("affected") or best.get("affected") or [])
        for field in ("summary", "details", "published", "modified", "severity", "references"):
            if not best.get(field):
                donor = max(group, key=lambda item: bool(item.get(field)))
                if donor.get(field):
                    best[field] = deepcopy(donor[field])
        merged.append(best)
    return sorted(merged, key=lambda item: cve_id(item) or item.get("id", ""))


def advisory_receipts(advisory: dict, result: WebResult) -> list[dict]:
    canonical = cve_id(advisory) or advisory.get("id", "unknown")
    title = safe_excerpt(advisory.get("summary") or canonical, 180)
    receipts = [{
        "publisher": "OSV",
        "title": title,
        "url": f"https://osv.dev/vulnerability/{advisory.get('id', canonical)}",
        "retrieved_at": result.retrieved_at,
        "mode": result.mode,
        "quote": safe_excerpt(advisory.get("summary") or advisory.get("details"), 700),
    }]
    references = advisory.get("references") or []
    for reference in references:
        url = reference.get("url") if isinstance(reference, dict) else None
        if not isinstance(url, str) or not url.startswith("https://") or any(url == row["url"] for row in receipts):
            continue
        if reference.get("type") in {"ADVISORY", "WEB"}:
            receipts.append({"publisher": "Linked advisory", "title": safe_excerpt(reference.get("type", "Advisory"), 80), "url": url[:1000], "retrieved_at": result.retrieved_at, "mode": result.mode, "quote": "Primary reference linked by the OSV record"})
        if len(receipts) == 3:
            break
    return receipts


class VulnerabilityIntel:
    def __init__(self, db: Database, web: CachedWebClient, osv_ttl: int = 3600, kev_ttl: int = 21600):
        self.db = db
        self.web = web
        self.osv_ttl = osv_ttl
        self.kev_ttl = kev_ttl

    async def query_package(self, dependency: Dependency) -> PackageIntel:
        key = f"osv:{dependency.ecosystem}:{dependency.name}:{dependency.version}"
        result = await self.web.request_json("POST", OSV_QUERY, key, self.osv_ttl, payload={
            "package": {"name": dependency.name, "ecosystem": dependency.ecosystem},
            "version": dependency.version,
        })
        if result.error:
            return PackageIntel(dependency, [], result)
        candidates = [item for item in (result.data or {}).get("vulns", []) if advisory_affects(item, dependency.name, dependency.ecosystem, dependency.version)]
        return PackageIntel(dependency, deduplicate(candidates), result)

    async def kev(self) -> WebResult:
        return await self.web.request_json("GET", KEV_URL, "cisa:kev", self.kev_ttl)


def kev_entries(result: WebResult) -> dict[str, dict]:
    if result.error:
        return {}
    return {item["cveID"]: item for item in (result.data or {}).get("vulnerabilities", []) if isinstance(item, dict) and isinstance(item.get("cveID"), str)}


def kev_receipt(cve: str, result: WebResult) -> dict:
    entry = kev_entries(result).get(cve, {})
    quote = f"CISA Known Exploited Vulnerabilities catalog lists {cve}."
    if entry.get("dueDate"):
        quote += f" Federal remediation due date: {entry['dueDate']}."
    return {"publisher": "CISA", "title": "Known Exploited Vulnerabilities Catalog", "url": KEV_URL, "retrieved_at": result.retrieved_at, "mode": result.mode, "quote": quote}


def score_and_severity(advisory: dict) -> tuple[float | None, str]:
    score = advisory_cvss(advisory)
    return score, severity_for(score, advisory)
