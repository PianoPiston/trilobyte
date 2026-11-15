import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, boxOf, fmtValue, unionBox } from "../api";
import type { Answer, Candidate, DrawingFull, Evidence, Word } from "../api";
import Viewer from "../components/Viewer";
import type { ViewerHandle } from "../components/Viewer";
import AnswerCard from "../components/AnswerCard";
import ContextPanel from "../components/ContextPanel";

type Tab = "evidence" | "data" | "context" | "about";
const LANGS = [["en", "EN"], ["fi", "FI"], ["all", "All"]];

export default function DrawingView() {
  const { id = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const [d, setD] = useState<DrawingFull | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState(sp.get("q") || "");
  const [lang, setLang] = useState("en");
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState<Answer | null>(null);
  const [cand, setCand] = useState<Candidate | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [showLayer, setShowLayer] = useState(false);
  const [showWords, setShowWords] = useState(false);
  const [words, setWords] = useState<Word[] | null>(null);
  const [wordsMsg, setWordsMsg] = useState("");
  const [tab, setTab] = useState<Tab>("evidence");
  const viewer = useRef<ViewerHandle>(null);
  const tabBody = useRef<HTMLDivElement>(null);

  const ask = async (question: string, dd = d) => {
    if (!dd || question.trim().length < 2) return;
    setQ(question); setBusy(true); setErr(null); setSel(null); setCand(null); setTab("evidence");
    try {
      const a = await api.ask(dd.id, question, lang === "all" ? undefined : lang);
      setAns(a);
      setSp({ q: question }, { replace: true });
      viewer.current?.focus(unionBox(a.evidence));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    setD(null); setAns(null); setErr(null); setSel(null); setCand(null); setWords(null); setShowWords(false); setShowLayer(false); setWordsMsg("");
    api.drawing(id).then((x) => {
      setD(x);
      setTab(x.track === "historic" ? "context" : "evidence");
      const q0 = sp.get("q");
      if (q0) ask(q0, x);
    }).catch((e) => setErr(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (sel) tabBody.current?.querySelector(`[data-ev="${CSS.escape(sel)}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [sel]);

  if (!d) return <div className="page"><div className={err ? "error" : "loading"}>{err ? `Could not load the drawing: ${err}` : "Loading…"}</div></div>;

  const evidence = (cand || ans)?.evidence || [];
  const pickCand = (c: Candidate | null) => {
    setCand(c); setSel(null);
    viewer.current?.focus(unionBox((c || ans)?.evidence || []));
  };
  const toggleWords = () => {
    setShowWords(!showWords);
    if (words !== null || wordsMsg) return;
    setWordsMsg("reading…");
    api.words(d.id)
      .then((w) => { setWords(w.words); setWordsMsg(w.available ? `${w.words.length} words, ${w.method === "pdf" ? "PDF text" : "OCR"}` : "none found"); })
      .catch(() => setWordsMsg("failed"));
  };
  const byLang = lang === "all" ? d.examples : d.examples.filter((e) => e.lang === lang);
  const examples = (byLang.length ? byLang : d.examples).slice(0, 4);
  const tabs: [Tab, string, boolean][] = [
    ["evidence", `Evidence${evidence.length ? ` ${evidence.length}` : ""}`, true],
    ["data", "Extracted data", !!d.standardized],
    ["context", "Archive context", !!d.context],
    ["about", "Source", true],
  ];

  return (
    <div className="workspace">
      <section className="sheet">
        <div className="sheet-head">
          <Link to="/" className="back" aria-label="Back to drawings">←</Link>
          <h1 title={d.title}>{d.title}</h1>
          <span className="sheet-meta">{d.source_label} · {d.formats.join(", ")}</span>
        </div>
        <Viewer ref={viewer} src={d.image_url} size={d.image_size} evidence={evidence}
          layer={showLayer ? d.std_layer : null} words={showWords ? words : null}
          hoverId={hover} selectedId={sel} onHover={setHover}
          onSelect={(s) => { setSel(s); if (s) setTab("evidence"); }}>
          {d.std_layer && d.std_layer.length > 0 && (
            <button className={showLayer ? "on" : ""} aria-pressed={showLayer} onClick={() => setShowLayer(!showLayer)}
              title="Outline every room, door, window and element extracted from this drawing">Extracted elements <span>{d.std_layer.length}</span></button>
          )}
          {d.track === "modern" && (
            <button className={showWords ? "on" : ""} aria-pressed={showWords} onClick={toggleWords}
              title="Printed text read from the drawing: PDF vector text, or OCR for scans">Printed text{wordsMsg && <span>{wordsMsg}</span>}</button>
          )}
        </Viewer>
        <p className="credit" title={d.credit || ""}>
          {d.licence} · {d.credit}
          {d.source_url && <> · <a href={d.source_url} target="_blank" rel="noreferrer noopener">source</a></>}
        </p>
      </section>

      <aside className="panel">
        <form className="ask" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
          <div className="ask-row">
            <input value={q} onChange={(e) => setQ(e.target.value)} aria-label="Question"
              placeholder={lang === "fi" ? "Kuinka monta makuuhuonetta piirustuksessa on?" : "How many bedrooms are there?"} />
            <button type="submit" disabled={busy || q.trim().length < 2}>Ask</button>
          </div>
          <div className="examples">
            {examples.map((e, i) => <button type="button" key={i} onClick={() => ask(e.question)} title={e.question}>{e.question}</button>)}
          </div>
          <div className="seg small" title="Language of the example questions and the answer">
            {LANGS.map(([k, label]) => <button type="button" key={k} className={lang === k ? "on" : ""} onClick={() => setLang(k)}>{label}</button>)}
          </div>
        </form>

        {err && <p className="error" role="alert">{err}</p>}
        {busy && <div className="answer-card loading-card"><span className="spinner" />Finding the answer…</div>}
        {!busy && ans && <AnswerCard a={ans} activeCand={cand?.id ?? null} onCandidate={pickCand} />}

        <div className="tabs" role="tablist">
          {tabs.filter((t) => t[2]).map(([k, label]) =>
            <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{label}</button>)}
        </div>
        <div ref={tabBody}>
          {tab === "evidence" && <EvidenceList items={evidence} ans={ans} hover={hover} sel={sel} onHover={setHover}
            onPick={(e) => { setSel(e.id); const b = boxOf(e); if (b) viewer.current?.focus(b); }} />}
          {tab === "data" && d.standardized && <DataPanel s={d.standardized} url={d.standardized_url} />}
          {tab === "context" && d.context && <ContextPanel c={d.context} />}
          {tab === "about" && <About d={d} />}
        </div>
      </aside>
    </div>
  );
}

function EvidenceList({ items, ans, hover, sel, onHover, onPick }: {
  items: Evidence[]; ans: Answer | null; hover: string | null; sel: string | null;
  onHover: (id: string | null) => void; onPick: (e: Evidence) => void;
}) {
  if (!items.length) {
    return (
      <p className="pane muted">
        {!ans ? "Ask a question and the items behind the answer are listed here and marked on the drawing."
          : ans.method === "cache" ? "This answer was cached from an evaluation run, which stored no evidence regions."
          : "This answer has no evidence that can be drawn on the sheet."}
      </p>
    );
  }
  return (
    <ul className="ev-list">
      {items.map((e, i) => (
        <li key={e.id + i} data-ev={e.id} className={(hover === e.id ? "hov " : "") + (sel === e.id ? "sel" : "")}
          onMouseEnter={() => onHover(e.id)} onMouseLeave={() => onHover(null)} onClick={() => onPick(e)}>
          <span className="ev-label">{e.label}</span>
          {e.off_sheet && <span className="muted">not on this sheet</span>}
          {e.approximate && <span className="muted">approximate</span>}
          {e.element_id && e.element_id !== e.label && <code title="Element id in the standardized file">{e.element_id}</code>}
        </li>
      ))}
    </ul>
  );
}

function DataPanel({ s, url }: { s: any; url: string | null }) {
  if (s.error) return <p className="pane muted">Converter error: {s.error}</p>;
  const stats = Object.entries<number>(s.counts || {}).filter(([, v]) => v > 0);
  const kinds = (o: Record<string, number> | undefined) => Object.entries(o || {}).map(([k, v]) => `${v} ${k}`).join(", ");
  return (
    <div className="pane">
      <p>
        {s.ground_truth_eligible
          ? "Parsed exactly from the CAD or BIM source file."
          : "Predicted by the symbol detector. These values are model output and are kept separate from ground truth."}
      </p>
      <div className="stats">
        {stats.map(([k, v]) => <div key={k}><b>{v}</b>{k}</div>)}
        {s.total_room_area_m2 > 0 && <div><b>{s.total_room_area_m2}</b>m² of rooms</div>}
      </div>
      {kinds(s.symbol_kinds) && <p className="muted">Symbols: {kinds(s.symbol_kinds)}</p>}
      {kinds(s.element_kinds) && <p className="muted">Elements: {kinds(s.element_kinds)}</p>}
      {s.levels?.length > 0 && <p className="muted">Storeys: {s.levels.join(", ")}</p>}
      {s.rooms?.length > 0 && (
        <table className="rooms">
          <thead><tr><th>Room</th><th>No.</th><th className="num">Area m²</th></tr></thead>
          <tbody>{s.rooms.slice(0, 80).map((r: any) => (
            <tr key={r.id}><td>{r.name || <span className="muted">unnamed</span>}</td><td>{r.number}</td>
              <td className="num" title={r.area_method}>{fmtValue(r.area_m2).value}</td></tr>
          ))}</tbody>
        </table>
      )}
      {s.warnings?.length > 0 && <p className="muted">Warnings: {s.warnings.join("; ")}</p>}
      {url && <a href={url} target="_blank" rel="noreferrer">Open the standardized JSON file ↗</a>}
    </div>
  );
}

function About({ d }: { d: DrawingFull }) {
  return (
    <dl className="kv pane">
      <div><dt>Collection</dt><dd>{d.source_label}</dd></div>
      <div><dt>Dataset split</dt><dd>{d.split ? `${d.split}${d.seen_in_training === false ? ", never used in training" : ""}` : "outside the question set"}</dd></div>
      <div><dt>Files</dt><dd>{Object.keys(d.files).join(", ").toUpperCase()}</dd></div>
      <div><dt>Licence</dt><dd>{d.licence}{d.licence?.includes("NC") && ", non-commercial use only"}</dd></div>
      <div><dt>Credit</dt><dd>{d.credit}</dd></div>
      {d.source_url && <div><dt>Original</dt><dd><a href={d.source_url} target="_blank" rel="noreferrer noopener">{d.source_url}</a></dd></div>}
    </dl>
  );
}
