import { useEffect, useState } from "react";
import { api } from "../api";

type Metric = "accuracy" | "accuracy_on_answered" | "answered_share";
const SYSTEMS = [
  { key: "zero-shot Qwen3.5-4B", label: "Zero-shot Qwen3.5-4B" },
  { key: "fine-tuned Qwen3.5-4B (LoRA)", label: "Fine-tuned Qwen3.5-4B" },
  { key: "hybrid router (DXF + IFC + fine-tuned VLM)", label: "Trilobyte router" },
];
const ROUTER = SYSTEMS[2].key;
const METRICS: [Metric, string][] = [["accuracy", "Accuracy on all questions"], ["accuracy_on_answered", "Accuracy on auto-answered"], ["answered_share", "Share auto-answered"]];
const SOURCES: Record<string, string> = { all: "All test questions", cubicasa5k: "CubiCasa raster plans", swiss_dwellings: "Swiss floors (PNG + DXF)",
  ifc_models: "IFC models", ifc_bench: "IFC-Bench free text", opening_design: "OpeningDesign sheets" };
const pct = (v: number | null | undefined, digits = 1) => (v == null ? "n/a" : `${(v * 100).toFixed(digits)}%`);
const plain = (s: string) => s.replace(/\*\*|`/g, "");

function MdTable({ t }: { t: { header: string[]; rows: string[][] } }) {
  return (
    <div className="table-wrap"><table className="data">
      <thead><tr>{t.header.map((h, i) => <th key={i}>{plain(h)}</th>)}</tr></thead>
      <tbody>{t.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={/^[\d.,€\-–]+$/.test(plain(c)) ? "num" : ""}>{plain(c)}</td>)}</tr>)}</tbody>
    </table></div>
  );
}

export default function Benchmark() {
  const [b, setB] = useState<any>(null);
  const [metric, setMetric] = useState<Metric>("accuracy");
  useEffect(() => { api.benchmark().then(setB); }, []);
  if (!b) return <div className="page"><div className="loading">Loading…</div></div>;
  const ps = b.per_source;
  const all = ps[ROUTER].all;
  const sources = Object.keys(ps[ROUTER]).filter((k) => !k.startsWith("_")).sort((x, y) => (x === "all" ? -1 : y === "all" ? 1 : ps[ROUTER][y].n - ps[ROUTER][x].n));
  return (
    <div className="page bench">
      <h1>Results on the held-out test set</h1>
      <p className="lead">{all.n.toLocaleString("en")} deduplicated questions on drawings that were never used in training. Counts must be exact and areas within 2%.</p>

      <div className="tiles">
        {SYSTEMS.map((s) => (
          <div key={s.key} className={s.key === ROUTER ? "hl" : ""}>
            <span>{s.label}</span><b>{pct(ps[s.key].all.accuracy)}</b><span>€{ps[s.key]._eur_per_1k} per 1k questions</span>
          </div>
        ))}
        <div className="hl">
          <span>Precision when auto-answering</span><b>{pct(all.accuracy_on_answered)}</b>
          <span>on the {pct(all.answered_share, 0)} of questions above confidence {b.threshold}</span>
        </div>
      </div>

      <div className="seg">
        {METRICS.map(([k, label]) => <button key={k} className={metric === k ? "on" : ""} onClick={() => setMetric(k)}>{label}</button>)}
      </div>
      <div className="chart">
        {sources.map((src) => (
          <div className="chart-group" key={src}>
            <div className="chart-cat">{SOURCES[src] || src}<span>n = {ps[ROUTER][src].n.toLocaleString("en")}</span></div>
            <div>
              {SYSTEMS.map((s, i) => {
                const v = ps[s.key]?.[src]?.[metric];
                return (
                  <div className="chart-row" key={s.key} title={`${s.label}: ${pct(v)}`}>
                    <span className="chart-sys">{s.label}</span>
                    <span className="chart-track"><span className={"chart-bar s" + i} style={{ width: pct(v ?? 0) }} /></span>
                    <span className="chart-val">{pct(v, 0)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <h2>Headline runs</h2>
      <MdTable t={b.headline} />
      <h2>Confidence calibration on validation</h2>
      <MdTable t={b.calibration} />
      {b.historic?.map((t: any, i: number) => <div key={i}><h2>{t.section}</h2><MdTable t={t} /></div>)}
      <ul className="notes">{b.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}</ul>
      {b.runs && (
        <details>
          <summary>All {b.runs.rows.length} evaluation runs</summary>
          <MdTable t={b.runs} />
        </details>
      )}
    </div>
  );
}
