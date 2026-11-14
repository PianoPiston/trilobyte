import { useState } from "react";
import type { Answer } from "../api";
import { fmtValue } from "../api";

export const METHOD_META: Record<string, { label: string; cls: string; hint: string }> = {
  "dxf-exact": { label: "Exact from CAD", cls: "m-exact", hint: "Parsed from the DXF vector file: deterministic, polygon evidence." },
  "ifc-exact": { label: "Exact from IFC model", cls: "m-exact", hint: "Queried from the BIM model with ifcopenshell: element GlobalIds as evidence." },
  detector: { label: "Detector", cls: "m-detector", hint: "Symbols found by our detector on the raster plan (model-derived file)." },
  vlm: { label: "AI model", cls: "m-vlm", hint: "Fine-tuned Qwen3.5-4B (LoRA), confidence = answer-token probability." },
  cache: { label: "AI model · cached", cls: "m-cache", hint: "Answer the AI model gave earlier (model endpoint offline right now)." },
  context: { label: "Archive record", cls: "m-context", hint: "Read from the drawing's archive record, with the source link." },
  none: { label: "No answer", cls: "m-none", hint: "No route could answer." },
};

export function MethodBadge({ m }: { m: string }) {
  const meta = METHOD_META[m] || METHOD_META.none;
  return <span className={"badge method " + meta.cls} title={meta.hint}>{meta.label}</span>;
}

export function costText(eur: number) {
  if (!eur) return "€0";
  const per1k = eur * 1000;
  return per1k < 0.01 ? `€${per1k.toFixed(4)} per 1k questions` : `€${per1k.toFixed(3)} per 1k questions`;
}

export default function AnswerCard({ a, onEvidence }: { a: Answer; onEvidence: () => void }) {
  const [trace, setTrace] = useState(false);
  const v = fmtValue(a.answer, a.unit);
  const conf = a.confidence;
  const placed = a.evidence.filter((e) => e.polygon || e.bbox).length;
  const status = a.answer === null ? "none" : a.needs_check ? "check" : "ok";
  return (
    <div className={"answer-card st-" + status}>
      <div className="answer-top">
        <MethodBadge m={a.method} />
        {a.method === "cache" && a.cached_method && <span className="muted small">originally {METHOD_META[a.cached_method]?.label || a.cached_method}</span>}
        <span className="grow" />
        {a.ground_truth_eligible && <span className="badge gt" title="Deterministic route over the source CAD/BIM data">ground-truth grade</span>}
      </div>
      <div className="answer-value">
        <span className="v">{v.value}</span>{v.unit && <span className="u">{v.unit}</span>}
      </div>
      {status === "ok" && <div className="verdict ok">✓ Answered automatically. {placed > 0 ? `Check the ${placed} highlighted item${placed > 1 ? "s" : ""} on the drawing.` : ""}</div>}
      {status === "check" && (
        <div className="verdict check">
          <b>⚠ Needs check</b>
          <ul>{a.needs_check_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </div>
      )}
      {status === "none" && <div className="verdict none"><b>{a.suggested_answer != null ? "No reliable answer." : "No answer."}</b> {a.needs_check_reasons.join(" ")}</div>}
      {a.note && <div className="note">{a.note}</div>}

      <div className="meters">
        <div className="meter">
          <div className="meter-label">Confidence</div>
          <div className="bar"><div className={"fill " + (conf !== null && conf >= 0.7 ? "hi" : "lo")} style={{ width: `${Math.round((conf ?? 0) * 100)}%` }} /><div className="thr" title="auto-answer threshold 0.7" /></div>
          <div className="meter-val">{conf === null ? "n/a" : `${Math.round(conf * 100)}%`}</div>
        </div>
        <div className="chips">
          <span className="chip" title="Inference cost of this query at batch-serving prices">💶 {costText(a.cost_eur)}</span>
          <span className="chip" title="Server-side latency">⏱ {a.latency_ms} ms</span>
          {placed > 0 && <button className="chip link" onClick={onEvidence}>◎ {placed} evidence item{placed > 1 ? "s" : ""}</button>}
        </div>
      </div>

      {a.reference && (
        <div className={"reference " + (a.reference.match === true ? "match" : a.reference.match === false ? "miss" : "")}>
          <span className="muted">Dataset label (hidden from the system):</span>{" "}
          <b>{fmtValue(a.reference.answer, a.reference.unit).value} {fmtValue(a.reference.answer, a.reference.unit).unit}</b>{" "}
          {a.reference.match === true ? "✓ match" : a.reference.match === false ? "✗ differs" : ""}
        </div>
      )}

      {a.sources.length > 0 && (
        <div className="sources">
          <div className="muted small">Sources</div>
          {a.sources.filter((s) => s.url).map((s, i) => (
            <a key={i} href={s.url!} target="_blank" rel="noreferrer noopener">{s.label} ↗</a>
          ))}
        </div>
      )}

      <button className="linklike small" onClick={() => setTrace(!trace)}>{trace ? "▾" : "▸"} How this was answered</button>
      {trace && (
        <ol className="trace">
          {a.route_trace.map((t, i) => <li key={i}><b>{t.route}</b>: {t.result}</li>)}
          {a.method_detail && <li className="muted">rule: <code>{a.method_detail}</code></li>}
        </ol>
      )}
    </div>
  );
}
