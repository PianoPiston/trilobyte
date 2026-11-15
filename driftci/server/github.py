"""Explicitly approved pull-request creation through GitHub's Git Data API."""
from __future__ import annotations

import base64
import re
from urllib.parse import quote

import httpx

from .remediation import patch_text


class GitHubError(RuntimeError):
    pass


class GitHubPullRequests:
    def __init__(self, http: httpx.AsyncClient, token: str):
        self.http = http
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        try:
            response = await self.http.request(method, f"https://api.github.com{path}", headers=self.headers, json=payload)
        except httpx.HTTPError as exc:
            raise GitHubError(f"GitHub API request failed: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise GitHubError(f"GitHub API returned HTTP {response.status_code} for {path.split('?')[0]}")
        return response.json()

    async def open(self, workspace: dict, remediation: dict, signal: dict) -> dict:
        owner, repository = workspace.get("repository", "").split("/", 1) if workspace.get("repository", "").count("/") == 1 else ("", "")
        valid = re.compile(r"^[A-Za-z0-9_.-]+$")
        if not valid.fullmatch(owner) or not valid.fullmatch(repository):
            raise GitHubError("The workspace is not connected to a GitHub repository")
        base = workspace.get("branch", "main")
        if not isinstance(base, str) or ".." in base or base.startswith("-"):
            raise GitHubError("The workspace branch is invalid")
        root = f"/repos/{owner}/{repository}"
        base_ref = await self._request("GET", f"{root}/git/ref/heads/{quote(base, safe='')}")
        base_sha = base_ref.get("object", {}).get("sha")
        if not isinstance(base_sha, str):
            raise GitHubError("GitHub did not return the base commit")
        tree = []
        for row in remediation["files"]:
            encoded = base64.b64encode(row["after"].encode()).decode()
            blob = await self._request("POST", f"{root}/git/blobs", {"content": encoded, "encoding": "base64"})
            tree.append({"path": row["path"], "mode": "100644", "type": "blob", "sha": blob["sha"]})
        new_tree = await self._request("POST", f"{root}/git/trees", {"base_tree": base_sha, "tree": tree})
        message = f"driftci: {remediation['title']}"
        commit = await self._request("POST", f"{root}/git/commits", {"message": message, "tree": new_tree["sha"], "parents": [base_sha]})
        branch = f"driftci/{remediation['id']}"
        await self._request("POST", f"{root}/git/refs", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
        citations = "\n".join(f"- [{receipt.get('publisher', 'Source')}: {receipt.get('title', 'Advisory')}]({receipt.get('url')})" for receipt in signal.get("source_receipts", []))
        body = f"Human-approved DriftCI remediation for **{signal['id']}**.\n\n{signal.get('recommendation', '')}\n\n## Targeted checks\n" + "\n".join(f"- {check['name']}: {check['status']} — {check['detail']}" for check in remediation["checks"])
        body += f"\n\n## Primary sources\n{citations}\n\nRepository tests were not executed by DriftCI. Static validation only.\n\n<details><summary>Unified patch</summary>\n\n```diff\n{patch_text(remediation)}```\n</details>"
        pr = await self._request("POST", f"{root}/pulls", {"title": message, "head": branch, "base": base, "body": body[:60000]})
        return {"pr_url": pr.get("html_url"), "pr_number": pr.get("number")}
