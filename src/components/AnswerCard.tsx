import type { Answer, Candidate } from "../api";
import { fmtValue } from "../api";

const METHODS: Record<string, { label: string; hint: string }> = {
  "dxf-exact": { label: "Exact from CAD", hint: "Computed from the DXF vector file. Deterministic, with polygon evidence." },
  "ifc-exact": { label: "Exact from IFC model", hint: "Queried from the BIM model. Evidence is the element GlobalIds." },
  detector: { label: "Symbol detector", hint: "Symbols found by the detector on the raster plan." },
  vlm: { label: "AI model", hint: "Fine-tuned Qwen3.5-4B. Confidence is the answer-token probability." },
  cache: { label: "AI model, cached", hint: "Answer the AI model gave earlier; the model endpoint is offline." },
  text: { label: "Printed text", hint: "Read from text printed on the drawing (PDF text or OCR) and assigned to the matching room." },
  context: { label: "Archive record", hint: "Read from the drawing's archive record, with the source link." },
  none: { label: "No route answered", hint: "No route could answer this question." },
};

const DECIDERS: Record<string, string> = {
  exact: "the exact file takes priority", deterministic: "ranked by calibrated rules",
  judge: "ranked by the decision model", "judge-fallback": "decision model failed, ranked by calibrated rules",
};

const pct = (c: number | null) => (c === null ? "n/a" : `${Math.round(c * 100)}%`);
const placedCount = (a: { evidence: Answer["evidence"] }) => a.evidence.filter((e) => e.polygon || e.bbox).length;

function costText(eur: number) {
  if (!eur) return "€0";
  const per1k = eur * 1000;
  return `€${per1k.toFixed(per1k < 0.01 ? 4 : 3)} per 1k questions`;
}

export default function AnswerCard({ a, activeCand, onCandidate }: {
  a: Answer; activeCand: string | null; onCandidate: (c: Candidate | null) => void;
}) {
  const v = fmtValue(a.answer, a.unit);
  const status = a.answer === null ? "none" : a.needs_check ? "check" : "ok";
  const method = METHODS[a.method] || METHODS.none;
  const placed = placedCount(a);
  const cands = (a.ranked_candidates || []).slice(a.answer === null ? 0 : 1);
  const ref = a.reference && fmtValue(a.reference.answer, a.reference.unit);
  const links = a.sources.filter((s) => s.url);
  return (
    <div className={"answer-card st-" + status}>
      <div className="answer-top">
        <span className="verdict">{status === "ok" ? "Answered automatically" : status === "check" ? "Needs check" : "No reliable answer"}</span>
        <span className={"method" + (a.ground_truth_eligible ? " exact" : "")} title={method.hint}>{method.label}</span>
      </div>
      <div className="answer-value">
        <span className="v">{v.value}</span>{v.unit && <span className="u">{v.unit}</span>}
      </div>
      {status === "ok" && placed > 0 && <p className="answer-note">Computed from the {placed} item{placed > 1 ? "s" : ""} highlighted on the drawing.</p>}
      {status !== "ok" && a.needs_check_reasons.length > 0 && (
        <ul className="reasons">{a.needs_check_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
      )}
      {a.note && <p className="answer-note">{a.note}</p>}

      <dl className="facts">
        <dt>Confidence</dt>
        <dd className="conf">
          <span className="bar"><span className="fill" style={{ width: pct(a.confidence ?? 0) }} /><span className="thr" title="Auto-answer threshold 70%" /></span>
          {pct(a.confidence)}
        </dd>
        <dt>Cost</dt><dd>{costText(a.cost_eur)}</dd>
        <dt>Latency</dt><dd>{a.latency_ms} ms</dd>
        {ref && (
          <>
            <dt title="The dataset label is looked up after the decision and is never shown to the system">Dataset label</dt>
            <dd className={a.reference!.match === true ? "match" : a.reference!.match === false ? "miss" : ""}>
              {ref.value} {ref.unit}{a.reference!.match === true ? " · matches" : a.reference!.match === false ? " · differs" : ""}
            </dd>
          </>
        )}
      </dl>

      {cands.length > 0 && (
        <div className="cands">
          <h3>{a.answer === null ? "Candidates" : "Other candidates"}<span> · {DECIDERS[a.decider || "deterministic"] || a.decider}</span></h3>
          {cands.map((c) => {
            const fv = fmtValue(c.value, c.unit);
            return (
              <button key={c.id} className={"cand" + (activeCand === c.id ? " on" : "")} title="Show this candidate's evidence on the drawing"
                onClick={() => onCandidate(activeCand === c.id ? null : c)}>
                <span className="cv">{fv.value} {fv.unit}</span>
                <span className="cs">{c.source_label || c.source}{c.agree_with.length > 0 && `, same as ${c.agree_with.join(", ")}`}</span>
                <span className="cc">{pct(c.confidence)}</span>
                {c.reason && <span className="cr">{c.reason}</span>}
              </button>
            );
          })}
        </div>
      )}

      {links.length > 0 && (
        <div className="sources">
          {links.map((s, i) => <a key={i} href={s.url!} target="_blank" rel="noreferrer noopener">{s.label} ↗</a>)}
        </div>
      )}

      <details className="trace">
        <summary>How this was answered</summary>
        <ol>
          {a.route_trace.map((t, i) => <li key={i}><b>{t.route}</b>: {t.result}</li>)}
          {a.method_detail && <li>Rule <code>{a.method_detail}</code></li>}
        </ol>
      </details>
    </div>
  );
}
