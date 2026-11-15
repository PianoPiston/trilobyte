from __future__ import annotations

import json

import httpx
from fastapi.testclient import TestClient

from server.app import create_app

from conftest import make_settings


NEXT_ADVISORY = {
    "id": "GHSA-f82v-jwr5-mffw", "aliases": ["CVE-2025-29927"], "summary": "Next.js middleware authorization bypass",
    "details": "Authorization checks in middleware require review on affected Next.js versions.",
    "published": "2025-03-21T00:00:00Z",
    "affected": [{
        "package": {"name": "next", "ecosystem": "npm"},
        "ranges": [{"type": "SEMVER", "events": [{"introduced": "14.0.0"}, {"fixed": "14.2.25"}]}],
    }],
    "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N"}],
    "references": [{"type": "ADVISORY", "url": "https://github.com/advisories/GHSA-f82v-jwr5-mffw"}],
}


def test_mocked_live_osv_and_kev_refresh_is_deduplicated_and_cached(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(str(request.url))
        if str(request.url) == "https://api.osv.dev/v1/query":
            body = json.loads(request.content)
            package = body["package"]["name"]
            vulns = [NEXT_ADVISORY] if package == "next" else []
            # A second OSV/CVE record with an adjacent alias is deliberately included.
            if package == "next":
                vulns.append(dict(NEXT_ADVISORY, id="CVE-2025-29927", aliases=["GHSA-f82v-jwr5-mffw"]))
            return httpx.Response(200, json={"vulns": vulns})
        if request.url.host == "www.cisa.gov":
            return httpx.Response(200, json={"vulnerabilities": [{"cveID": "CVE-2025-29927", "dueDate": "2025-04-01", "knownRansomwareCampaignUse": "Unknown"}]})
        raise AssertionError(f"Unexpected network request: {request.url}")

    transport = httpx.MockTransport(handler)
    with TestClient(create_app(make_settings(tmp_path, offline=False), transport)) as client:
        response = client.post("/api/scan")
        assert response.status_code == 200, response.text
        payload = response.json()
        signal = next(row for row in payload["signals"] if row["id"] == "sig-CVE-2025-29927")
        assert signal["kev"] is True
        assert signal["cvss"] == 9.1
        assert signal["fixed_version"] == "14.2.25"
        assert signal["source_receipts"][0]["mode"] == "live"
        assert signal["source_receipts"][0]["url"].endswith("GHSA-f82v-jwr5-mffw") or signal["source_receipts"][0]["url"].endswith("CVE-2025-29927")
        assert any(row["publisher"] == "CISA" for row in signal["source_receipts"])
        assert len([row for row in payload["signals"] if row["id"] == "sig-CVE-2025-29927"]) == 1
        assert len(payload["history"]) == 1
        assert len(calls) == 4  # Three exact dependencies and one KEV feed; Context.dev is unconfigured.
        first_retrieval = signal["source_receipts"][0]["retrieved_at"]
        second = client.post("/api/scan").json()
        assert len(calls) == 4
        cached = next(row for row in second["signals"] if row["id"] == "sig-CVE-2025-29927")
        assert cached["source_receipts"][0]["mode"] == "cached"
        assert cached["source_receipts"][0]["retrieved_at"] == first_retrieval
        remediation = client.post("/api/remediations", json={"signal_id": signal["id"]}).json()
        assert len(remediation["files"]) == 1
        assert '"next": "14.2.25"' in remediation["files"][0]["after"]
        assert any(check["status"] == "pending" and check["name"] == "Repository tests" for check in remediation["checks"])
