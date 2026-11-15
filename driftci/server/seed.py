"""Deterministic, explicitly labelled offline workspace and historical evidence."""
from __future__ import annotations

from copy import deepcopy

from .scanner import Dependency, dependency_evidence, model_evidence

DEMO_WORKSPACE = {
    "id": "demo",
    "name": "Orders AI",
    "repository": "junction/orders-ai",
    "branch": "main",
    "environment": "Production",
    "source": "demo",
}
DEPRECATION_URL = "https://developers.openai.com/api/docs/deprecations"
DEPRECATION_QUOTE = "Mar 26, 2026: gpt-4-0314 — recommended replacement gpt-5, or gpt-4.1 for latency-sensitive tasks"
NEXT_CVE_URL = "https://osv.dev/vulnerability/GHSA-f82v-jwr5-mffw"

DEMO_FILES = {
    "package.json": '''{
  "name": "orders-ai",
  "private": true,
  "dependencies": {
    "@ai-sdk/openai": "0.0.66",
    "next": "14.2.3",
    "openai": "4.77.0",
    "react": "18.3.1",
    "zod": "3.23.8"
  }
}
''',
    "package-lock.json": '''{
  "name": "orders-ai",
  "lockfileVersion": 3,
  "packages": {
    "": {
      "dependencies": {
        "@ai-sdk/openai": "0.0.66",
        "next": "14.2.3",
        "openai": "4.77.0",
        "react": "18.3.1",
        "zod": "3.23.8"
      }
    },
    "node_modules/@ai-sdk/openai": { "version": "0.0.66" },
    "node_modules/next": { "version": "14.2.3" },
    "node_modules/openai": { "version": "4.77.0" },
    "node_modules/react": { "version": "18.3.1" },
    "node_modules/zod": { "version": "3.23.8" }
  }
}
''',
    "src/lib/ai.ts": '''import OpenAI from "openai";

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

export type SupportAsset = "Support summaries" | "Escalation drafts";

export const SUMMARY_MODEL = "gpt-4-0314";
export const REVIEW_MODEL = "o1-mini";

export async function summarize(input: string) {
  const response = await openai.responses.create({ model: SUMMARY_MODEL, input });
  return response.output_text;
}
''',
    "src/lib/escalation.ts": '''import OpenAI from "openai";

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
export const ESCALATION_MODEL = "gpt-4-0314";

export async function draftEscalation(input: string) {
  const response = await openai.responses.create({ model: ESCALATION_MODEL, input });
  return response.output_text;
}
''',
    "src/app/api/support/route.ts": '''import { summarize } from "@/lib/ai";
import { draftEscalation } from "@/lib/escalation";

export async function POST(request: Request) {
  const { message, escalate } = await request.json();
  const text = escalate ? await draftEscalation(message) : await summarize(message);
  return Response.json({ text });
}
''',
    "middleware.ts": '''import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const session = request.cookies.get("session");
  if (!session && request.nextUrl.pathname.startsWith("/operations")) {
    return NextResponse.redirect(new URL("/sign-in", request.url));
  }
  return NextResponse.next();
}
''',
    "next.config.mjs": '''/** @type {import('next').NextConfig} */
const nextConfig = { poweredByHeader: false };
export default nextConfig;
''',
    "README.md": '''# Orders AI

Support operations built with Next.js and the OpenAI API. Model identifiers are kept in
`src/lib` so evaluations can pin explicit snapshots. Do not commit API credentials.
''',
}


def actions(fixed: str, acknowledged_at: str | None = None) -> list[dict]:
    rows = [
        ("ack", "Acknowledge incident", "Assign an incident owner"),
        ("contain", "Contain exposure", "Apply temporary compensating controls documented for this advisory"),
        ("patch", "Apply fixed version", f"Upgrade to {fixed} or a later unaffected release" if fixed else "Upgrade to an unaffected release"),
        ("verify", "Verify remediation", "Confirm the resolved dependency version and run application security tests"),
        ("resolve", "Resolve & document", "Record residual risk and close the incident"),
    ]
    return [{"id": ident, "label": label, "detail": detail, "status": "done" if ident == "ack" and acknowledged_at else "pending", "completed_at": acknowledged_at if ident == "ack" else None} for ident, label, detail in rows]


def deprecation_receipt(mode: str = "historical_replay", retrieved_at: str = "2026-03-26T00:00:00Z", quote: str = DEPRECATION_QUOTE) -> dict:
    return {"publisher": "OpenAI", "title": "Model deprecations", "url": DEPRECATION_URL, "retrieved_at": retrieved_at, "mode": mode, "quote": quote[:700]}


def deprecation_signal(files: dict[str, str] | None = None, receipt: dict | None = None) -> dict:
    files = files or DEMO_FILES
    evidence = [{key: value for key, value in item.items() if key != "model"} for item in model_evidence(files, "gpt-4-0314")]
    return {
        "id": "sig-model-gpt4-0314",
        "kind": "deprecation",
        "severity": "critical",
        "state": "needs_action",
        "title": "A retired model is still configured",
        "summary": f"gpt-4-0314 was shut down on 26 Mar 2026. {len(evidence)} production call sites still select it.",
        "provider": "OpenAI",
        "affected_assets": ["Support summaries", "Escalation drafts"],
        "deadline": "2026-03-26T00:00:00Z",
        "announced_at": "2025-09-26T00:00:00Z",
        "cve": None,
        "cvss": None,
        "kev": False,
        "fixed_version": None,
        "replacement": "gpt-4.1",
        "reachability": "confirmed",
        "reachability_reason": "Exact model identifiers in source confirm configuration, not invocation at runtime.",
        "recommendation": "Replace the snapshot identifier with gpt-4.1 and run the existing evaluation workflow before deployment.",
        "evidence": evidence,
        "source_receipts": [receipt or deprecation_receipt()],
        "remediation_id": None,
        "created_at": "2025-09-26T00:00:00Z",
    }


def vulnerability_pair(files: dict[str, str] | None = None) -> tuple[dict, dict]:
    files = files or DEMO_FILES
    dependency = Dependency("next", "npm", "14.2.3", "14.2.3", "framework", "package.json", True)
    evidence = dependency_evidence(files, dependency)
    middleware = [item for item in evidence if "middleware" in item["file"]]
    receipt = {
        "publisher": "OSV / GitHub Advisory Database",
        "title": "Next.js middleware authorization bypass",
        "url": NEXT_CVE_URL,
        "retrieved_at": "2025-03-21T00:00:00Z",
        "mode": "historical_snapshot",
        "quote": "CVE-2025-29927; next 14.2.3 is in the affected range; the advisory lists 14.2.25 as fixed.",
    }
    signal = {
        "id": "sig-CVE-2025-29927",
        "kind": "vulnerability",
        "severity": "critical",
        "state": "needs_action",
        "title": "Next.js middleware authorization bypass",
        "summary": "The installed Next.js release falls within the advisory's affected range. Middleware presence makes review urgent; exploitability still requires deployment verification.",
        "provider": "Vercel",
        "affected_assets": ["Middleware authorization"],
        "deadline": None,
        "cve": "CVE-2025-29927",
        "cvss": 9.1,
        "kev": False,
        "fixed_version": "14.2.25",
        "replacement": None,
        "reachability": "likely" if middleware else "unknown",
        "reachability_reason": "middleware.ts contains authorization logic; verify deployment behavior before relying on this heuristic.",
        "recommendation": "Upgrade next to 14.2.25 or later and run application authorization tests.",
        "evidence": evidence,
        "source_receipts": [receipt],
        "remediation_id": None,
        "created_at": "2025-03-21T00:00:00Z",
        "affected_package": "next",
        "ecosystem": "npm",
        "affected_version": "14.2.3",
    }
    incident = {
        "id": "inc-CVE-2025-29927",
        "cve": "CVE-2025-29927",
        "title": "Next.js middleware authorization bypass",
        "severity": "critical",
        "cvss": 9.1,
        "kev": False,
        "state": "triaging",
        "first_seen_at": "2025-03-21T00:00:00Z",
        "resolved_at": None,
        "affected_package": "next",
        "affected_version": "14.2.3",
        "fixed_version": "14.2.25",
        "reachability": signal["reachability"],
        "reachability_reason": signal["reachability_reason"],
        "summary": signal["summary"],
        "affected_files": middleware or evidence,
        "source_receipts": [receipt],
        "actions": actions("14.2.25", "2025-03-21T00:10:00Z"),
        "signal_id": signal["id"],
    }
    return signal, incident


def history_pair(files: dict[str, str] | None = None) -> tuple[dict, dict]:
    files = files or DEMO_FILES
    receipt = {
        "publisher": "OSV / GitHub Advisory Database",
        "title": "Next.js Server-Side Request Forgery in Server Actions",
        "url": "https://osv.dev/vulnerability/GHSA-fr5h-rqp8-mj6g",
        "retrieved_at": "2024-05-09T00:00:00Z",
        "mode": "historical_snapshot",
        "quote": "CVE-2024-34351 was fixed in Next.js 14.1.1; the workspace is now on a later release.",
    }
    evidence = dependency_evidence(files, Dependency("next", "npm", "14.2.3", "14.2.3", "framework", "package.json", True))
    signal = {
        "id": "sig-CVE-2024-34351", "kind": "vulnerability", "severity": "high", "state": "resolved",
        "title": "Next.js Server-Side Request Forgery in Server Actions",
        "summary": "Historical incident. The advisory was remediated by moving to Next.js 14.1.1 or later.",
        "provider": "Vercel", "affected_assets": ["Server Actions"], "deadline": None,
        "cve": "CVE-2024-34351", "cvss": 7.5, "kev": False, "fixed_version": "14.1.1", "replacement": None,
        "reachability": "not_assessed", "reachability_reason": "Historical record; runtime reachability was not established.",
        "recommendation": "Retain the fixed release and regression coverage.", "evidence": evidence,
        "source_receipts": [receipt], "remediation_id": None, "created_at": "2024-05-09T00:00:00Z",
        "affected_package": "next", "ecosystem": "npm", "affected_version": "14.1.0",
    }
    done_actions = actions("14.1.1")
    for action in done_actions:
        action.update(status="done", completed_at="2024-05-09T01:42:00Z")
    incident = {
        "id": "inc-CVE-2024-34351", "cve": "CVE-2024-34351", "title": signal["title"], "severity": "high",
        "cvss": 7.5, "kev": False, "state": "resolved", "first_seen_at": "2024-05-09T00:00:00Z",
        "resolved_at": "2024-05-09T01:42:00Z", "affected_package": "next", "affected_version": "14.1.0",
        "fixed_version": "14.1.1", "reachability": "not_assessed", "reachability_reason": signal["reachability_reason"],
        "summary": signal["summary"], "affected_files": [], "source_receipts": [receipt], "actions": done_actions,
        "signal_id": signal["id"],
    }
    return signal, incident


def demo_records(files: dict[str, str] | None = None) -> dict:
    files = files or DEMO_FILES
    model = deprecation_signal(files)
    current_signal, current_incident = vulnerability_pair(files)
    old_signal, old_incident = history_pair(files)
    sources = [
        {"id": "src-openai-deprecations", "publisher": "OpenAI", "title": "Model deprecations", "url": DEPRECATION_URL, "status": "replay", "last_checked_at": "2026-03-26T00:00:00Z", "event_count": 1, "mode": "historical_replay", "error": None},
        {"id": "src-osv", "publisher": "OSV", "title": "Open vulnerability intelligence", "url": "https://osv.dev", "status": "historical_snapshot", "last_checked_at": "2025-03-21T00:00:00Z", "event_count": 2, "mode": "historical_snapshot", "error": None},
    ]
    activity = [
        {"id": "a-demo-replay", "type": "replay", "title": "Historical incident ready", "detail": "OpenAI announced gpt-4-0314 retirement on 26 Sep 2025; shutdown was 26 Mar 2026.", "created_at": "2026-03-26T00:00:00Z"},
        {"id": "a-demo-seed", "type": "scan", "title": "Controlled demo workspace loaded", "detail": f"{len(files)} files indexed · historical advisory snapshot, not a live vulnerability scan", "created_at": "2025-03-21T00:00:00Z"},
    ]
    return {"workspace": deepcopy(DEMO_WORKSPACE), "files": deepcopy(files), "signals": [model, current_signal, old_signal], "incidents": [current_incident, old_incident], "sources": sources, "activity": activity}
