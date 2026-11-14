import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, fmtValue } from "../api";
import type { Answer, DrawingFull, Example } from "../api";
import Viewer, { boxOf } from "../components/Viewer";
import type { ViewerHandle } from "../components/Viewer";
import AnswerCard from "../components/AnswerCard";
import ContextPanel from "../components/ContextPanel";
import { DrawingBadges, CreditLine } from "../components/Badges";

const LANGS = [{ k: "en", label: "EN" }, { k: "fi", label: "FI" }, { k: "all", label: "All" }];

export default function DrawingView() {
  const { id = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const [d, setD] = useState<DrawingFull | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState(sp.get("q") || "");
  const [lang, setLang] = useState("en");
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState<Answer | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [showLayer, setShowLayer] = useState(false);
  const [tab, setTab] = useState<"evidence" | "std" | "context" | "about">("evidence");
  const viewer = useRef<ViewerHandle>(null);
  const evList = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setD(null); setAns(null); setErr(null); setSel(null);
    api.drawing(id).then((x) => {
      setD(x);
      setTab(x.track === "historic" ? "context" : "evidence");
      const q0 = sp.get("q");
      if (q0) ask(q0, x);
    }).catch((e) => setErr(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const ask = async (question: string, dd = d) => {
    if (!dd || question.trim().length < 2) return;
    setQ(question); setBusy(true); setSel(null); setTab("evidence");
    try {
      const a = await api.ask(dd.id, question, lang === "all" ? undefined : lang);
      setAns(a);
      setSp({ q: question }, { replace: true });
      const placed = a.evidence.filter((e) => e.polygon || e.bbox);
      if (placed.length) {
        const bs = placed.map(boxOf).filter(Boolean) as number[][];
        viewer.current?.focus([Math.min(...bs.map((b) => b[0])), Math.min(...bs.map((b) => b[1])), Math.max(...bs.map((b) => b[2])), Math.max(...bs.map((b) => b[3]))]);
      } else viewer.current?.fit();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const examples: Example[] = useMemo(() => {
    if (!d) return [];
    const ex = lang === "all" ? d.examples : d.examples.filter((e) => e.lang === lang);
    return ex.length ? ex : d.examples;
  }, [d, lang]);

  useEffect(() => {
    if (!sel || !evList.current) return;
    evList.current.querySelector(`[data-ev="${CSS.escape(sel)}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [sel]);

  if (err && !d) return <div className="page"><div className="error">Could not load drawing: {err}</div></div>;
  if (!d) return <div className="page"><div className="loading">Loading…</div></div>;

  const evidence = ans?.evidence || [];
  const placeholder = lang === "fi" ? "Kysy piirustuksesta, esim. Kuinka monta makuuhuonetta?" : "Ask about this drawing, e.g. How many bedrooms are there?";

  return (
    <div className="drawing-page">
      <section className="left">
        <div className="drawing-head">
          <Link to="/" className="back">← Drawings</Link>
          <div className="dh-title">
            <h1 title={d.title}>{d.title}</h1>
            <DrawingBadges d={d} />
          </div>
          {d.std_layer && d.std_layer.length > 0 && (
            <label className="toggle" title="Draw every room, door, window and element of the standardized file">
              <input type="checkbox" checked={showLayer} onChange={(e) => setShowLayer(e.target.checked)} /> Standardized layer ({d.std_layer.length})
            </label>
          )}
        </div>
        <Viewer ref={viewer} src={d.image_url} size={d.image_size} evidence={evidence} layer={d.std_layer} showLayer={showLayer}
          hoverId={hover} selectedId={sel} onHover={setHover}
          onSelect={(s) => { setSel(s); if (s) setTab("evidence"); }} />
        <CreditLine d={d} />
      </section>

      <aside className="right">
        <form className="ask" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
          <div className="ask-row">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} aria-label="Question" />
            <button type="submit" disabled={busy || q.trim().length < 2}>{busy ? "…" : "Ask"}</button>
          </div>
          <div className="ask-sub">
            <div className="seg">
              {LANGS.map((l) => <button type="button" key={l.k} className={lang === l.k ? "on" : ""} onClick={() => setLang(l.k)}>{l.label}</button>)}
            </div>
            <span className="muted small">{d.track === "historic" ? "Hand-labelled examples:" : "Examples from the dataset:"}</span>
          </div>
          <div className="examples">
            {examples.slice(0, 8).map((e, i) => (
              <button type="button" key={i} className="ex" onClick={() => ask(e.question)} title={e.question}>{e.question}</button>
            ))}
            {examples.length === 0 && <span className="muted small">No dataset questions for this drawing; ask anything.</span>}
          </div>
        </form>

        {busy && <div className="answer-card loading-card"><div className="spinner" /> Routing the question…</div>}
        {!busy && ans && <AnswerCard a={ans} onEvidence={() => setTab("evidence")} />}
        {!busy && !ans && (
          <div className="hint-card">
            <b>How it works.</b> Each question goes to the cheapest route that can answer it exactly (CAD/IFC parsers), then to the
            fine-tuned model. Every answer shows its method, confidence, cost and the evidence on the drawing.
          </div>
        )}

        <div className="tabs">
          <button className={tab === "evidence" ? "on" : ""} onClick={() => setTab("evidence")}>Evidence{evidence.length ? ` (${evidence.length})` : ""}</button>
          {d.standardized && <button className={tab === "std" ? "on" : ""} onClick={() => setTab("std")}>Standardized data</button>}
          {d.context && <button className={tab === "context" ? "on" : ""} onClick={() => setTab("context")}>Context</button>}
          <button className={tab === "about" ? "on" : ""} onClick={() => setTab("about")}>Drawing</button>
        </div>

        <div className="tab-body" ref={evList}>
          {tab === "evidence" && (
            evidence.length === 0 ? <div className="muted small pad">{ans ? (ans.method === "cache" ? "Cached answers from the evaluation run carry no boxes. With the model online, the base model draws pointer boxes." : "This answer has no drawable evidence.") : "Ask a question to see its evidence."}</div> :
              <ul className="ev-list">
                {evidence.map((e, i) => (
                  <li key={e.id + i} data-ev={e.id}
                    className={(hover === e.id ? "hov " : "") + (sel === e.id ? "sel " : "") + (e.off_sheet ? "off" : "")}
                    onMouseEnter={() => setHover(e.id)} onMouseLeave={() => setHover(null)}
                    onClick={() => { setSel(e.id); const b = boxOf(e); if (b) viewer.current?.focus(b); }}>
                    <span className={"kind k-" + (e.kind || "item")}>{e.kind || "item"}</span>
                    <span className="ev-label">{e.label}</span>
                    {e.element_id && <code className="ev-id" title="element id in the standardized file">{e.element_id}</code>}
                    {e.off_sheet && <span className="muted small"> not on this sheet</span>}
                    {e.approximate && <span className="muted small"> approx.</span>}
                  </li>
                ))}
              </ul>
          )}
          {tab === "std" && d.standardized && <StdPanel s={d.standardized} url={d.standardized_url} />}
          {tab === "context" && d.context && <ContextPanel c={d.context} />}
          {tab === "about" && <AboutDrawing d={d} />}
        </div>
      </aside>
    </div>
  );
}

function StdPanel({ s, url }: { s: any; url: string | null }) {
  if (s.error) return <div className="muted small pad">Converter error: {s.error}</div>;
  const c = s.counts || {};
  return (
    <div className="std pad">
      <p className="small">
        <b>{s.producer?.kind === "exact" ? "Exact standardized file" : "Model-derived file"}</b> · <code>{s.schema_version}</code> · converter <code>{s.producer?.converter}</code>
        {s.ground_truth_eligible ? <span className="badge gt">ground-truth eligible</span> : <span className="badge warn">model output, not ground truth</span>}
      </p>
      <div className="stat-row">
        {Object.entries(c).filter(([, v]) => (v as number) > 0).map(([k, v]) => <div className="stat" key={k}><div className="n">{v as number}</div><div className="k">{k}</div></div>)}
        {s.total_room_area_m2 > 0 && <div className="stat"><div className="n">{s.total_room_area_m2}</div><div className="k">m² rooms</div></div>}
      </div>
      {Object.keys(s.symbol_kinds || {}).length > 0 && <p className="small">Symbols: {Object.entries(s.symbol_kinds).map(([k, v]) => `${v} ${k}`).join(", ")}</p>}
      {Object.keys(s.element_kinds || {}).length > 0 && <p className="small">Elements: {Object.entries(s.element_kinds).map(([k, v]) => `${v} ${k}`).join(", ")}</p>}
      {s.levels?.length > 0 && <p className="small">Storeys: {s.levels.join(" · ")}</p>}
      {s.rooms?.length > 0 && (
        <table className="mini">
          <thead><tr><th>Room</th><th>No.</th><th>Area</th><th>Source</th></tr></thead>
          <tbody>{s.rooms.slice(0, 80).map((r: any) => (
            <tr key={r.id}><td>{r.name || <span className="muted">unnamed</span>}</td><td>{r.number}</td>
              <td className="num">{r.area_m2 != null ? fmtValue(r.area_m2, "m2").value : "—"}</td><td className="muted">{r.area_method}</td></tr>
          ))}</tbody>
        </table>
      )}
      {s.registration && <p className="muted small">DXF → sheet registration: {s.registration.px_per_m} px/m, fit score {s.registration.score}.</p>}
      {s.warnings?.length > 0 && <p className="muted small">Warnings: {s.warnings.join("; ")}</p>}
      {url && <a className="small" href={url} target="_blank" rel="noreferrer">Open the full standardized JSON ↗</a>}
    </div>
  );
}

function AboutDrawing({ d }: { d: DrawingFull }) {
  return (
    <div className="pad small">
      <dl className="kv">
        <dt>Source</dt><dd>{d.source_label}</dd>
        <dt>Split</dt><dd>{d.split ? `${d.split}${d.seen_in_training === false ? " (not seen in training)" : ""}` : "not in the question set"}</dd>
        <dt>Files</dt><dd>{Object.entries(d.files).map(([k, v]) => <div key={k}><code>{k}</code> {v}</div>)}</dd>
        <dt>Licence</dt><dd>{d.licence}</dd>
        <dt>Credit</dt><dd>{d.credit}</dd>
        {d.source_url && <><dt>Original</dt><dd><a href={d.source_url} target="_blank" rel="noreferrer">{d.source_url}</a></dd></>}
      </dl>
    </div>
  );
}
