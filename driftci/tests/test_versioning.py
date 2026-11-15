from __future__ import annotations

from server.intel import cve_id, deduplicate
from server.versioning import Version, advisory_affects, advisory_cvss, fixed_version


def advisory() -> dict:
    return {
        "id": "GHSA-f82v-jwr5-mffw", "aliases": ["CVE-2025-29927"], "summary": "Next.js middleware authorization bypass",
        "affected": [{
            "package": {"name": "next", "ecosystem": "npm"},
            "ranges": [{"type": "SEMVER", "events": [{"introduced": "14.0.0"}, {"fixed": "14.2.25"}]}],
        }],
        "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"}],
    }


def test_osv_ranges_fixed_version_and_cvss():
    row = advisory()
    assert advisory_affects(row, "next", "npm", "14.2.3")
    assert not advisory_affects(row, "next", "npm", "14.2.25")
    assert not advisory_affects(row, "react", "npm", "14.2.3")
    assert fixed_version(row, "next", "npm", "14.2.3") == "14.2.25"
    assert advisory_cvss(row) == 9.1


def test_semver_prerelease_and_series_ordering():
    assert Version.parse("14.2.25-rc.1") < Version.parse("14.2.25")
    assert Version.parse("14.2.25-1") < Version.parse("14.2.25-alpha")
    assert Version.parse("14.2") == Version.parse("14.2.0")


def test_alias_records_are_deduplicated_transitively():
    first = advisory()
    second = dict(first, id="CVE-2025-29927", aliases=["GHSA-f82v-jwr5-mffw"])
    third = dict(first, id="GHSA-unrelated", aliases=["CVE-2099-0001"])
    rows = deduplicate([first, second, third])
    assert len(rows) == 2
    merged = next(row for row in rows if cve_id(row) == "CVE-2025-29927")
    assert set(merged["_ids"]) == {"CVE-2025-29927", "GHSA-f82v-jwr5-mffw"}
