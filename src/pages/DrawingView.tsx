import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, boxOf, unionBox } from "../api";
import type { Answer, Candidate, DrawingFull, Evidence, Word } from "../api";
import { DEFAULTS, fetchPrices, fetchTakeoff, fmt, materialLines, roomName, totals } from "../lib/takeoff";
import { materialIntent } from "../lib/intent";
import type { Intent } from "../lib/intent";
import type { Prices, Takeoff } from "../lib/takeoff";
import Viewer from "../components/Viewer";
import type { Measure, Tool, ViewerHandle } from "../components/Viewer";
import AnswerCard from "../components/AnswerCard";
import ContextPanel from "../components/ContextPanel";
import SummaryPanel from "../components/SummaryPanel";
import MaterialsPanel from "../components/MaterialsPanel";
import TakeoffAnswer from "../components/TakeoffAnswer";

const Scene3D = lazy(() => import("../components/Scene3D"));

type Tab = "summary" | "materials" | "answer" | "archive" | "source";
const TOOLS: [Tool, string, string][] = [
  ["select", "Select", "Pan the plan and click rooms"],
  ["distance", "Distance", "Click two points to measure a length"],
  ["area", "Area", "Click the corners of a region, then click the first point or press Enter"],
  ["calibrate", "Set scale", "Click the two ends of a length you know"],
];

export default function DrawingView() {
  const { id = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const [d, setD] = useState<DrawingFull | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState(sp.get("q") || "");
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState<Answer | null>(null);
  const [local, setLocal] = useState<Intent | null>(null);
  const [cand, setCand] = useState<Candidate | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [showRooms, setShowRooms] = useState(true);
  const [showLayer, setShowLayer] = useState(false);
  const [showWords, setShowWords] = useState(false);
  const [words, setWords] = useState<Word[] | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [takeoff, setTakeoff] = useState<Takeoff | null>(null);
  const [takeoffErr, setTakeoffErr] = useState(false);
  const [ownScale, setOwnScale] = useState<number | null>(null);
  const [calib, setCalib] = useState<{ px: number; metres: string } | null>(null);
  const [tool, setTool] = useState<Tool>("select");
  const [measures, setMeasures] = useState<Measure[]>([]);
  const [mode, setMode] = useState<"2d" | "3d">("2d");
  const [roomId, setRoomId] = useState<string | null>(null);
  const [a, setA] = useState(DEFAULTS);
  const [prices, setPrices] = useState<Prices | null>(null);
  const viewer = useRef<ViewerHandle>(null);
  const tabBody = useRef<HTMLDivElement>(null);

  const ask = async (question: string, dd = d) => {
    if (!dd || question.trim().length < 2) return;
    setQ(question); setErr(null); setSel(null); setCand(null); setTab("answer"); setMode("2d");
    const intent = takeoff && (ownScale ?? takeoff.scale.m_per_px) ? materialIntent(question, takeoff.rooms) : null;
    setLocal(intent);
    if (intent) {
      setAns(null);
      setSp({ q: question }, { replace: true });
      viewer.current?.focus(unionBox(intent.rooms ?? takeoff!.rooms));
      return;
    }
    setBusy(true);
    try {
      const r = await api.ask(dd.id, question);
      setAns(r);
      setSp({ q: question }, { replace: true });
      viewer.current?.focus(unionBox(r.evidence));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    setD(null); setAns(null); setLocal(null); setErr(null); setSel(null); setCand(null); setWords(null); setShowWords(false); setShowLayer(false);
    setTakeoff(null); setTakeoffErr(false); setRoomId(null); setMeasures([]); setTool("select"); setMode("2d");
    setOwnScale(Number(localStorage.getItem(`scale:${id}`)) || null);
    api.drawing(id).then((x) => {
      setD(x);
      setTab(x.track === "historic" ? "archive" : "summary");
      const q0 = sp.get("q");
      if (q0) ask(q0, x);
    }).catch((e) => setErr(e.message));
    fetchTakeoff(id).then(setTakeoff).catch(() => setTakeoffErr(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => { fetchPrices().then(setPrices).catch(() => {}); }, []);
  // while the service is fetching live prices, poll until they arrive
  useEffect(() => {
    if (!prices?.refreshing) return;
    const t = window.setTimeout(() => fetchPrices().then(setPrices).catch(() => {}), 5000);
    return () => window.clearTimeout(t);
  }, [prices]);

  useEffect(() => {
    if (sel) tabBody.current?.querySelector(`[data-ev="${CSS.escape(sel)}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [sel]);

  const m = ownScale ?? takeoff?.scale.m_per_px ?? null;
  const room = takeoff?.rooms.find((r) => r.id === roomId) ?? null;
  const x = useMemo(() => (takeoff && m ? totals(takeoff, m, a, room ? [room] : null) : null), [takeoff, m, a, room]);
  const concrete = useMemo(() => {
    if (!takeoff || !m || !x) return null;
    const qty = materialLines(x, takeoff, m, a, !room)[0].qty;
    return { qty, cost: qty * (prices?.items.find((p) => p.key === "concrete")?.price ?? 0) };
  }, [takeoff, m, x, a, room, prices]);

  if (!d) return <div className="page"><div className={err ? "error" : "loading"}>{err ? `Could not load the drawing: ${err}` : "Loading…"}</div></div>;

  const evidence: Evidence[] = local
    ? (local.rooms ?? takeoff?.rooms ?? []).map((r) => ({ id: r.id, label: `${roomName(r)}${m ? ` · ${fmt(r.area_m2 ?? r.printed_area_m2 ?? r.area_px * m * m)} m²` : ""}`, polygon: r.polygon }))
    : (cand || ans)?.evidence || [];
  const pickCand = (c: Candidate | null) => {
    setCand(c); setSel(null);
    viewer.current?.focus(unionBox((c || ans)?.evidence || []));
  };
  const pickRoom = (rid: string | null) => {
    setRoomId(rid);
    const r = takeoff?.rooms.find((y) => y.id === rid);
    if (r && mode === "2d") viewer.current?.focus(boxOf(r));
    if (rid && tab !== "materials") setTab("summary");
  };
  const toggleWords = () => {
    setShowWords(!showWords);
    if (words === null) api.words(d.id).then((w) => setWords(w.words)).catch(() => setWords([]));
  };
  const applyScale = () => {
    const metres = Number(calib?.metres.replace(",", "."));
    if (!calib || !(metres > 0)) return;
    setOwnScale(metres / calib.px);
    localStorage.setItem(`scale:${id}`, String(metres / calib.px));
    setCalib(null); setTool("select");
  };
  const resetScale = () => { setOwnScale(null); localStorage.removeItem(`scale:${id}`); };
  const scaleNote = ownScale ? "set by you from a known length" : takeoff?.scale.method;
  const unsure = !ownScale && (takeoff?.scale.confidence ?? 0) < 0.6;
  const tabs: [Tab, string, boolean][] = [
    ["summary", "Summary", true], ["materials", "Materials", !!(takeoff && m)], ["answer", "Answer", true],
    ["archive", "Archive", !!d.context], ["source", "Source", true],
  ];

  return (
    <div className="workspace">
      <section className="sheet">
        <div className="sheet-head">
          <Link to="/" className="back" aria-label="Back to drawings">←</Link>
          <h1 title={d.title}>{d.title}</h1>
          <span className="sheet-meta">{d.source_label} · {d.formats.join(", ")}</span>
          <div className="seg small mode">
            <button className={mode === "2d" ? "on" : ""} onClick={() => setMode("2d")}>Plan</button>
            <button className={mode === "3d" ? "on" : ""} disabled={!takeoff || !m} onClick={() => setMode("3d")}
              title={takeoff && m ? "3D model built from this drawing" : "The 3D model needs rooms and a scale"}>3D model</button>
          </div>
        </div>

        {mode === "3d" && takeoff && m ? (
          <Suspense fallback={<div className="viewer"><div className="viewer-loading">Building the 3D model…</div></div>}>
            <Scene3D takeoff={takeoff} mPerPx={m} imageUrl={d.image_url} wallHeight={a.wallHeight} roomId={roomId} onRoom={pickRoom} />
          </Suspense>
        ) : (
          <Viewer ref={viewer} src={d.image_url} size={d.image_size} evidence={evidence}
            layer={showLayer ? d.std_layer : null} words={showWords ? words : null}
            rooms={showRooms ? takeoff?.rooms ?? null : null} mPerPx={m} roomId={roomId} onRoom={pickRoom}
            tool={tool} measures={measures} onMeasure={(ms) => setMeasures([...measures, ms])}
            onCalibrate={(px) => setCalib({ px, metres: "" })}
            hoverId={hover} selectedId={sel} onHover={setHover}
            onSelect={(s) => { setSel(s); if (s) setTab("answer"); }}>
            <div className="toolbar">
              {TOOLS.map(([k, label, hint]) => <button key={k} className={tool === k ? "on" : ""} title={hint} onClick={() => setTool(k)}>{label}</button>)}
              {measures.length > 0 && <button onClick={() => setMeasures([])}>Clear</button>}
            </div>
            <div className="layers">
              {takeoff && takeoff.rooms.length > 0 && <button className={showRooms ? "on" : ""} aria-pressed={showRooms} onClick={() => setShowRooms(!showRooms)}>Rooms</button>}
              {d.std_layer && d.std_layer.length > 0 && <button className={showLayer ? "on" : ""} aria-pressed={showLayer} onClick={() => setShowLayer(!showLayer)}>Doors, windows, fixtures</button>}
              <button className={showWords ? "on" : ""} aria-pressed={showWords} onClick={toggleWords}>Printed text</button>
            </div>
            {tool !== "select" && !calib && <div className="hint">{TOOLS.find((t) => t[0] === tool)![2]}. Esc cancels.</div>}
            {calib && (
              <form className="calib" onSubmit={(e) => { e.preventDefault(); applyScale(); }}>
                <label>Real length of that line
                  <span className="num-input"><input autoFocus inputMode="decimal" value={calib.metres} onChange={(e) => setCalib({ ...calib, metres: e.target.value })} placeholder="0.90" />m</span>
                </label>
                <button type="submit">Set scale</button>
                <button type="button" className="link" onClick={() => setCalib(null)}>Cancel</button>
              </form>
            )}
            {takeoff && (
              <div className={"scale" + (unsure ? " unsure" : "")}>
                {m ? <><b>1 m = {fmt(1 / m, 0)} px</b> · {scaleNote}</> : <b>No scale yet</b>}
                {ownScale ? <button className="link" onClick={resetScale}>Reset</button>
                  : unsure && <button className="link" onClick={() => setTool("calibrate")}>Set it from a known length</button>}
              </div>
            )}
          </Viewer>
        )}
        <p className="credit" title={d.credit || ""}>
          {d.licence} · {d.credit}
          {d.source_url && <> · <a href={d.source_url} target="_blank" rel="noreferrer noopener">source</a></>}
        </p>
      </section>

      <aside className="panel">
        <form className="ask" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
          <div className="ask-row">
            <input value={q} onChange={(e) => setQ(e.target.value)} aria-label="Question"
              placeholder={room ? `Ask about ${room.name || "this room"}` : "Ask anything about this drawing"} />
            <button type="submit" disabled={busy || q.trim().length < 2}>Ask</button>
          </div>
        </form>

        <div className="tabs" role="tablist">
          {tabs.filter((t) => t[2]).map(([k, label]) =>
            <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{label}</button>)}
        </div>
        <div ref={tabBody} className="tab-body">
          {tab === "summary" && (
            takeoff ? <SummaryPanel takeoff={takeoff} m={m} x={x} room={room} concrete={concrete} onRoom={pickRoom} onAsk={ask} onMaterials={() => setTab("materials")} />
              : <p className="pane muted">{takeoffErr ? "The plan could not be measured." : "Measuring the plan…"}</p>
          )}
          {tab === "materials" && takeoff && m && x && (
            <MaterialsPanel takeoff={takeoff} m={m} x={x} room={room} a={a} setA={setA} prices={prices}
              onRefresh={() => fetchPrices(true).then(setPrices)} onClearRoom={() => setRoomId(null)} />
          )}
          {tab === "answer" && (
            <>
              {err && <p className="error" role="alert">{err}</p>}
              {busy && <div className="answer-card loading-card"><span className="spinner" />Finding the answer…</div>}
              {local && takeoff && m && <TakeoffAnswer intent={local} takeoff={takeoff} m={m} a={a} prices={prices} onMaterials={() => setTab("materials")} />}
              {!busy && ans && <AnswerCard a={ans} activeCand={cand?.id ?? null} onCandidate={pickCand} />}
              {!busy && !ans && !local && (
                <div className="pane">
                  <p className="muted">Answers appear here with the evidence marked on the plan.</p>
                  <div className="examples">{d.examples.filter((e) => e.lang === "en").slice(0, 6).map((e, i) =>
                    <button key={i} onClick={() => ask(e.question)} title={e.question}>{e.question}</button>)}</div>
                </div>
              )}
              {evidence.length > 0 && !(local && !local.rooms) && <EvidenceList items={evidence} hover={hover} sel={sel} onHover={setHover}
                onPick={(e) => { setSel(e.id); const b = boxOf(e); if (b) viewer.current?.focus(b); }} />}
            </>
          )}
          {tab === "archive" && d.context && <ContextPanel c={d.context} />}
          {tab === "source" && <About d={d} />}
        </div>
      </aside>
    </div>
  );
}

function EvidenceList({ items, hover, sel, onHover, onPick }: {
  items: Evidence[]; hover: string | null; sel: string | null; onHover: (id: string | null) => void; onPick: (e: Evidence) => void;
}) {
  return (
    <>
      <h3>Evidence</h3>
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
    </>
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
      {d.standardized_url && <div><dt>Extracted data</dt><dd><a href={d.standardized_url} target="_blank" rel="noreferrer">Standardized JSON file ↗</a></dd></div>}
      {d.source_url && <div><dt>Original</dt><dd><a href={d.source_url} target="_blank" rel="noreferrer noopener">{d.source_url}</a></dd></div>}
    </dl>
  );
}
