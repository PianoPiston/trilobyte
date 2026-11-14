import { useEffect, useState } from "react";
import { api } from "../api";

const SERIES = [
  { key: "zero-shot Qwen3.5-4B", short: "Zero-shot", color: "var(--series-1)" },
  { key: "fine-tuned Qwen3.5-4B (LoRA)", short: "Fine-tuned", color: "var(--series-2)" },
  { key: "hybrid router (DXF + IFC + fine-tuned VLM)", short: "Hybrid router", color: "var(--series-3)" },
];
const SRC_LABEL: Record<string, string> = { all: "All test questions", cubicasa5k: "CubiCasa (raster plans)", swiss_dwellings: "Swiss floors (PNG+DXF)",
  ifc_models: "IFC models", ifc_bench: "IFC-Bench (free text)", opening_design: "OpeningDesign sheets" };

function Bars({ ps, metric }: { ps: any; metric: "accuracy" | "accuracy_on_answered" | "answered_share" }) {
  const [tip, setTip] = useState<{ x: number; y: number; t: string } | null>(null);
  const sources = Object.keys(ps[SERIES[2].key] || {}).filter((k) => !k.startsWith("_")).sort((a, b) => (a === "all" ? -1 : b === "all" ? 1 : (ps[SERIES[2].key][b].n - ps[SERIES[2].key][a].n)));
  const rowH = 14, gap = 2, groupGap = 18, labelW = 190, plotW = 440;
  const groupH = SERIES.length * rowH + (SERIES.length - 1) * gap;
  const height = sources.length * (groupH + groupGap);
  return (
    <div className="chart" onMouseLeave={() => setTip(null)}>
      <div className="legend">{SERIES.map((s) => <span key={s.key}><i style={{ background: s.color }} />{s.short}</span>)}</div>
      <svg width={labelW + plotW + 60} height={height + 24} role="img" aria-label={`${metric} by source and system`}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}><line x1={labelW + t * plotW} x2={labelW + t * plotW} y1={0} y2={height} className="grid" />
            <text x={labelW + t * plotW} y={height + 16} className="axis" textAnchor="middle">{Math.round(t * 100)}%</text></g>
        ))}
        {sources.map((src, gi) => {
          const y0 = gi * (groupH + groupGap);
          return (
            <g key={src}>
              <text x={labelW - 10} y={y0 + groupH / 2 + 4} textAnchor="end" className="cat">{SRC_LABEL[src] || src}</text>
              <text x={labelW - 10} y={y0 + groupH / 2 + 17} textAnchor="end" className="axis">n = {ps[SERIES[2].key][src]?.n}</text>
              {SERIES.map((s, si) => {
                const v = ps[s.key]?.[src]?.[metric];
                const y = y0 + si * (rowH + gap);
                const w = v == null ? 0 : Math.max(2, v * plotW);
                return (
                  <g key={s.key} onMouseMove={(e) => setTip({ x: e.nativeEvent.offsetX + 12, y: e.nativeEvent.offsetY + 8, t: `${s.short} · ${SRC_LABEL[src] || src}: ${v == null ? "n/a" : (v * 100).toFixed(1) + "%"}` })}>
                    <rect x={labelW} y={y - 1} width={plotW} height={rowH + 2} fill="transparent" />
                    <path d={`M${labelW},${y} h${Math.max(0, w - 4)} a4,4 0 0 1 4,4 v${rowH - 8} a4,4 0 0 1 -4,4 h${-Math.max(0, w - 4)} z`} fill={s.color} />
                    <text x={labelW + w + 6} y={y + rowH - 3} className="val">{v == null ? "n/a" : `${Math.round(v * 100)}%`}</text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
      {tip && <div className="tip" style={{ left: tip.x, top: tip.y }}>{tip.t}</div>}
    </div>
  );
}

function MdTable({ t }: { t: any }) {
  if (!t) return null;
  const strip = (s: string) => s.replace(/\*\*/g, "").replace(/`/g, "");
  return (
    <div className="table-wrap"><table className="data">
      <thead><tr>{t.header.map((h: string, i: number) => <th key={i}>{strip(h)}</th>)}</tr></thead>
      <tbody>{t.rows.map((r: string[], i: number) => <tr key={i}>{r.map((c, j) => <td key={j} className={/^[\d.,€\-–]+$/.test(strip(c)) ? "num" : ""}>{strip(c)}</td>)}</tr>)}</tbody>
    </table></div>
  );
}

export default function Benchmark() {
  const [b, setB] = useState<any>(null);
  const [metric, setMetric] = useState<"accuracy" | "accuracy_on_answered" | "answered_share">("accuracy");
  const [showRuns, setShowRuns] = useState(false);
  useEffect(() => { api.benchmark().then(setB); }, []);
  if (!b) return <div className="page"><div className="loading">Loading…</div></div>;
  const ps = b.per_source;
  const hy = ps[SERIES[2].key]?.all, zs = ps[SERIES[0].key]?.all, ft = ps[SERIES[1].key]?.all;
  return (
    <div className="page bench">
      <h1 className="page-title">Benchmark: held-out test set</h1>
      <p className="muted">6,428 deduplicated questions on drawings never seen in training. Counts must be exact; areas within 2%.</p>
      <div className="tiles">
        <div className="tile"><div className="k">Zero-shot Qwen3.5-4B</div><div className="n">{(zs.accuracy * 100).toFixed(1)}%</div><div className="s">€{ps[SERIES[0].key]._eur_per_1k}/1k questions</div></div>
        <div className="tile"><div className="k">Fine-tuned (LoRA, Verda A100)</div><div className="n">{(ft.accuracy * 100).toFixed(1)}%</div><div className="s">€{ps[SERIES[1].key]._eur_per_1k}/1k questions</div></div>
        <div className="tile hl"><div className="k">Hybrid router (our product)</div><div className="n">{(hy.accuracy * 100).toFixed(1)}%</div><div className="s">€{ps[SERIES[2].key]._eur_per_1k}/1k questions</div></div>
        <div className="tile hl"><div className="k">Auto-answered (confidence ≥ {b.threshold})</div><div className="n">{(hy.accuracy_on_answered * 100).toFixed(1)}%</div><div className="s">correct on the {(hy.answered_share * 100).toFixed(0)}% it answers; the rest go to “Needs check”</div></div>
      </div>
      <div className="seg">
        {([["accuracy", "Accuracy (all questions)"], ["accuracy_on_answered", "Accuracy on auto-answered"], ["answered_share", "Share auto-answered"]] as const).map(([k, l]) =>
          <button key={k} className={metric === k ? "on" : ""} onClick={() => setMetric(k)}>{l}</button>)}
      </div>
      <Bars ps={ps} metric={metric} />
      <h2>Per source (table view)</h2>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Source</th><th>n</th>{SERIES.map((s) => <th key={s.key} colSpan={3}>{s.short}</th>)}</tr>
          <tr><th /><th />{SERIES.map((s) => [<th key={s.key + "a"}>acc</th>, <th key={s.key + "b"}>answered</th>, <th key={s.key + "c"}>acc on answered</th>])}</tr></thead>
        <tbody>{Object.keys(ps[SERIES[2].key]).filter((k) => !k.startsWith("_")).map((src) => (
          <tr key={src}><td>{SRC_LABEL[src] || src}</td><td className="num">{ps[SERIES[2].key][src].n}</td>
            {SERIES.map((s) => { const c = ps[s.key]?.[src] || {}; const f = (v: any) => (v == null ? "–" : (v * 100).toFixed(1) + "%");
              return [<td key={s.key + "a"} className="num">{f(c.accuracy)}</td>, <td key={s.key + "b"} className="num">{f(c.answered_share)}</td>, <td key={s.key + "c"} className="num">{f(c.accuracy_on_answered)}</td>]; })}
          </tr>))}</tbody>
      </table></div>
      <h2>Headline table (results/leaderboard.md)</h2>
      <MdTable t={b.headline} />
      <h2>Confidence calibration (validation, cubicasa)</h2>
      <MdTable t={b.calibration} />
      {b.historic?.map((t: any, i: number) => <div key={i}><h2>{t.section}</h2><MdTable t={t} /></div>)}
      <ul className="notes">{b.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}</ul>
      <button className="linklike" onClick={() => setShowRuns(!showRuns)}>{showRuns ? "▾" : "▸"} All evaluation runs ({b.runs?.rows.length})</button>
      {showRuns && <MdTable t={b.runs} />}
    </div>
  );
}
