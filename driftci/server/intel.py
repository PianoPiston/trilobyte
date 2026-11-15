"""Live OSV and CISA KEV clients plus deterministic advisory normalization."""
from __future__ import annotations

import asyncio
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import re
import time

from .db import Database
from .scanner import Dependency
from .util import safe_excerpt
from .versioning import advisory_affects, advisory_cvss, severity_for
from .web import CachedWebClient, WebResult

OSV_QUERY = "https://api.osv.dev/v1/query"
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
OSV_ECOSYSTEMS = {"npm", "pypi", "go", "maven", "crates.io", "rubygems", "packagist", "nuget", "pub", "hex", "alpine", "debian"}
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

    async def _advisory_details(self, identifier: str, deadline: float, semaphore: asyncio.Semaphore) -> tuple[dict | None, str | None]:
        """Expand a minimal querybatch descriptor into the range-bearing OSV record."""
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,160}", identifier):
            return None, "invalid advisory identifier"
        if time.monotonic() >= deadline:
            return None, "detail retrieval deadline reached"
        try:
            async with semaphore:
                async with asyncio.timeout(max(.001, deadline - time.monotonic())):
                    result = await self.web.request_json("GET", "https://api.osv.dev/v1/vulns/" + identifier, "osv-detail:" + identifier, self.osv_ttl)
        except (TimeoutError, asyncio.TimeoutError):
            return None, "detail retrieval deadline reached"
        data = result.data if not result.error and isinstance(result.data, dict) else None
        record = {"record": data, "mode": result.mode, "retrieved_at": result.retrieved_at} if data and data.get("id") == identifier and isinstance(data.get("affected"), list) else None
        return record, result.error or (None if record else "full advisory detail was unavailable or inconsistent")

    async def query_batch(self, dependencies: list[Dependency], *, limit: int, deadline: float, concurrency: int = 6) -> dict:
        """Cache exact package results independently while batching uncached queries."""
        supported = [dep for dep in dependencies if dep.advisory_supported and dep.ecosystem.lower() in OSV_ECOSYSTEMS]
        unresolved = [dep for dep in dependencies if not dep.exact]
        unsupported = [dep for dep in dependencies if dep not in supported and dep not in unresolved]
        limited = supported[:limit]
        unique: dict[tuple[str, str, str], Dependency] = {}
        occurrences: dict[tuple[str, str, str], list[Dependency]] = {}
        for dep in limited:
            identity = (dep.ecosystem.lower(), dep.name.lower(), dep.version.lower())
            unique.setdefault(identity, dep)
            occurrences.setdefault(identity, []).append(dep)
        cache_keys = {}
        for identity, dep in unique.items():
            encoded = json.dumps(identity, separators=(",", ":"))
            cache_keys[identity] = "osv-batch:" + hashlib.sha256(encoded.encode()).hexdigest()
        missing = []
        responses: dict[tuple[str, str, str], list[dict]] = {}
        checked_identities = set()
        live_identities = set()
        now = time.time()
        for identity, dep in unique.items():
            key = cache_keys[identity]
            entry = self.db.cache_get(key) if self.db.cache_fetched_at(key) + self.osv_ttl >= now else None
            if entry is not None and isinstance(entry.get("body"), list):
                responses[identity] = entry["body"]
                checked_identities.add(identity)
            else:
                missing.append((identity, dep))
        batches: list[list[tuple[tuple[str, str, str], Dependency]]] = []
        for offset in range(0, len(missing), 500):
            batches.append(missing[offset:offset + 500])
        started = time.monotonic()
        error = None
        completed_batches = 0
        live_batches = 0
        semaphore = asyncio.Semaphore(concurrency)

        async def request(batch):
            nonlocal error, live_batches
            if time.monotonic() >= deadline:
                return []
            async with semaphore:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return []
                try:
                    async with asyncio.timeout(remaining):
                        payload = {"queries": [{"package": {"name": dep.name, "ecosystem": dep.ecosystem}, "version": dep.version} for _identity, dep in batch]}
                        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                        result = await self.web.request_json("POST", OSV_BATCH, f"osv-querybatch:{digest}", self.osv_ttl, payload=payload)
                except (TimeoutError, asyncio.TimeoutError):
                    error = "OSV batch deadline reached; retained data does not imply safety for unchecked packages"
                    return []
                if result.error or not isinstance(result.data, dict) or not isinstance(result.data.get("results"), list) or len(result.data["results"]) != len(batch):
                    error = result.error or "OSV returned an incomplete batch response"
                    return []
                if any(isinstance(row, dict) and row.get("next_page_token") for row in result.data["results"]):
                    error = "OSV returned a next-page token; this run did not retrieve all advisory pages. Affected package versions remain pending."
                    return []
                if any(not isinstance(row, (dict, type(None))) or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in ((row or {}).get("vulns") or [])) for row in result.data["results"]):
                    error = "OSV returned an invalid advisory descriptor; affected package versions remain pending"
                    return []
                if result.mode == "live":
                    live_batches += 1
                    live_identities.update(identity for identity, _dep in batch)
                successful = []
                for (identity, _dep), row in zip(batch, result.data["results"]):
                    advisories = (row or {}).get("vulns", []) if isinstance(row, dict) or row is None else []
                    if not isinstance(advisories, list):
                        advisories = []
                    self.db.cache_set(cache_keys[identity], time.time(), {"body": advisories, "retrieved_at": result.retrieved_at})
                    responses[identity] = advisories
                    successful.append(identity)
                return successful

        results = await asyncio.gather(*(request(batch) for batch in batches)) if batches else []
        for batch in results:
            checked_identities.update(batch)
            completed_batches += 1
        if not completed_batches and missing and error is None:
            error = "OSV batch deadline reached before any query completed"
        # querybatch returns {id, modified} descriptors. Ranges require each detail record.
        detail_ids = sorted({item["id"] for items in responses.values() for item in items if isinstance(item, dict) and isinstance(item.get("id"), str) and not isinstance(item.get("affected"), list)})
        detail_semaphore = asyncio.Semaphore(concurrency)
        detail_results = await asyncio.gather(*(
            self._advisory_details(identifier, deadline, detail_semaphore) for identifier in detail_ids
        )) if detail_ids else []
        details = {identifier: result for identifier, (result, _error) in zip(detail_ids, detail_results) if result is not None}
        detail_errors = Counter(error for _identifier, (_result, error) in zip(detail_ids, detail_results) if error)
        incomplete_details = []
        for identity, items in responses.items():
            missing = [item["id"] for item in items if isinstance(item, dict) and isinstance(item.get("id"), str) and not isinstance(item.get("affected"), list) and item["id"] not in details]
            if missing:
                incomplete_details.extend(missing)
                checked_identities.discard(identity)
            else:
                responses[identity] = [details[item["id"]]["record"] if isinstance(item, dict) and item.get("id") in details else item for item in items]
                if any(isinstance(item, dict) and details.get(item.get("id", ""), {}).get("mode") == "live" for item in items):
                    live_identities.add(identity)
        if incomplete_details:
            reasons = "; ".join(f"{reason}: {count}" for reason, count in sorted(detail_errors.items()))
            error = f"{len(set(incomplete_details))} advisory detail records were not retrieved before the deadline; affected package versions remain pending" + (f" ({reasons})" if reasons else "")
        for identity in unique:
            if identity in live_identities:
                continue
            if any(details.get(item.get("id", ""), {}).get("mode") == "live" for item in responses.get(identity, []) if isinstance(item, dict)):
                live_identities.add(identity)
        records = []
        for identity, dep in unique.items():
            if identity not in responses:
                continue
            advisories = [item for item in responses[identity] if isinstance(item, dict) and isinstance(item.get("affected"), list) and advisory_affects(item, dep.name, dep.ecosystem, dep.version)]
            key = cache_keys[identity]
            cached = self.db.cache_get(key) or {}
            detail_times = [details[item["id"]]["retrieved_at"] for item in responses[identity] if isinstance(item, dict) and item.get("id") in details and details[item["id"]].get("retrieved_at")]
            retrieved_at = max([stamp for stamp in [cached.get("retrieved_at"), *detail_times] if isinstance(stamp, str) and stamp], default=None)
            # Every manifest occurrence needs its own evidence and scope. Query once
            # per exact version, then fan the advisory result out to those occurrences.
            for occurrence in occurrences[identity]:
                records.append(PackageIntel(occurrence, deduplicate(advisories), WebResult(responses[identity], "live" if identity in live_identities else "cached", retrieved_at)))
        pending = [dep for dep in limited if (dep.ecosystem.lower(), dep.name.lower(), dep.version.lower()) not in checked_identities]
        pending.extend(supported[limit:])
        return {
            "records": records, "error": error,
            "packages_total": len(dependencies), "packages_eligible": len(supported),
            "packages_checked": sum(1 for dep in supported if (dep.ecosystem.lower(), dep.name.lower(), dep.version.lower()) in checked_identities),
            "packages_pending": len(pending), "packages_unresolved": len(unresolved),
            "packages_unsupported": len(unsupported),
            "unsupported_packages": [{"name": dep.name, "version": dep.version, "ecosystem": dep.ecosystem, "certainty": dep.certainty} for dep in unsupported[:80]],
            "batch_count": len(batches), "batches_completed": completed_batches, "live_batches": live_batches, "cached_batches": completed_batches - live_batches,
            "advisory_details_requested": len(detail_ids), "advisory_details_retrieved": len(details),
            "advisory_details_pending": len(set(incomplete_details)),
            "advisory_detail_errors": dict(detail_errors),
            "complete": not pending,
            "seconds": round(time.monotonic() - started, 3),
        }

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
