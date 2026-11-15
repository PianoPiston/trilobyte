import { useState } from "react";
import { UNIT, eur, fmt, materialLines, roomName } from "../lib/takeoff";
import type { Assumptions, Prices, Room, Takeoff, Totals } from "../lib/takeoff";

const host = (u: string) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; } };
const ago = (iso: string) => {
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  return min < 1 ? "just now" : min < 60 ? `${min} min ago` : `${Math.round(min / 60)} h ago`;
};

function Num({ label, value, unit, step, onChange }: { label: string; value: number; unit: string; step: number; onChange: (v: number) => void }) {
  return (
    <label className="num-field">
      <span>{label}</span>
      <span className="num-input"><input type="number" value={value} step={step} min={0} onChange={(e) => onChange(Math.max(0, Number(e.target.value)))} />{unit}</span>
    </label>
  );
}

export default function MaterialsPanel({ takeoff, m, x, room, a, setA, prices, onRefresh, onClearRoom }: {
  takeoff: Takeoff; m: number; x: Totals; room: Room | null; a: Assumptions; setA: (a: Assumptions) => void;
  prices: Prices | null; onRefresh: () => void; onClearRoom: () => void;
}) {
  const [own, setOwn] = useState<Record<string, number>>({});
  const [open, setOpen] = useState<string | null>("concrete");
  const lines = materialLines(x, takeoff, m, a, !room);
  const price = (key: string) => own[key] ?? prices?.items.find((p) => p.key === key)?.price ?? 0;
  const total = lines.reduce((s, l) => s + l.qty * price(l.key), 0);
  const concrete = lines[0];

  return (
    <div className="materials">
      <div className="scope">
        <span>{room ? roomName(room) : "Whole floor"}</span>
        {room ? <button className="link" onClick={onClearRoom}>Show whole floor</button> : <span className="muted">Click a room on the plan to price it alone</span>}
      </div>

      <div className="hero-figure">
        <span className="eyebrow">Concrete to order for {room ? "this room" : "this floor"}</span>
        <div><b>{fmt(concrete.qty)}</b><span>m³</span><em>{eur(concrete.qty * price("concrete"))}</em></div>
        <p>{concrete.basis}, at {eur(price("concrete"))} per m³{prices?.items.find((q) => q.key === "concrete")?.live ? ", live web price" : ""}</p>
      </div>

      <div className="assumptions">
        <Num label="Slab thickness" value={a.slabCm} unit="cm" step={1} onChange={(v) => setA({ ...a, slabCm: v })} />
        <Num label="Wall height" value={a.wallHeight} unit="m" step={0.1} onChange={(v) => setA({ ...a, wallHeight: v })} />
        <Num label="Waste" value={a.wastePct} unit="%" step={1} onChange={(v) => setA({ ...a, wastePct: v })} />
      </div>

      <table className="bom">
        <thead><tr><th>Material</th><th className="num">Quantity</th><th className="num">Unit price</th><th className="num">Cost</th></tr></thead>
        <tbody>
          {lines.map((l) => {
            const p = prices?.items.find((q) => q.key === l.key);
            return [
              <tr key={l.key} className={open === l.key ? "open" : ""} onClick={() => setOpen(open === l.key ? null : l.key)}>
                <td>{l.label}<small>{p?.live && own[l.key] === undefined ? "Live price" : own[l.key] !== undefined ? "Your price" : "Reference price"}</small></td>
                <td className="num">{fmt(l.qty)} {UNIT[l.unit]}</td>
                <td className="num" onClick={(e) => e.stopPropagation()}>
                  <span className="num-input">€<input type="number" step="0.01" min={0} value={price(l.key)} aria-label={`Unit price of ${l.label}`}
                    onChange={(e) => setOwn({ ...own, [l.key]: Number(e.target.value) })} />/{UNIT[l.unit]}</span>
                </td>
                <td className="num">{eur(l.qty * price(l.key))}</td>
              </tr>,
              open === l.key && (
                <tr key={l.key + "d"} className="detail"><td colSpan={4}>
                  <p><span className="muted">Quantity</span> {l.basis}</p>
                  {p?.live ? (
                    <>
                      <p><span className="muted">Price</span> median of {p.n} listed price{p.n === 1 ? "" : "s"} found on the web, {eur(p.low!)} to {eur(p.high!)} per {UNIT[l.unit]}</p>
                      {p.sources!.map((s, i) => (
                        <blockquote key={i}>
                          <a href={s.url} target="_blank" rel="noreferrer noopener">{eur(s.price)} · {host(s.url)} ↗</a>
                          <span>{s.quote}</span>
                        </blockquote>
                      ))}
                    </>
                  ) : <p><span className="muted">Price</span> {p?.note || "Reference estimate."}</p>}
                </td></tr>
              ),
            ];
          })}
        </tbody>
        <tfoot><tr><td colSpan={3}>Materials total</td><td className="num">{eur(total)}</td></tr></tfoot>
      </table>

      <p className="fineprint">
        Prices are read from Finnish supplier and price-guide pages through context.dev web search
        {prices?.fetched_at ? `, last fetched ${ago(prices.fetched_at)}` : ""}. VAT and delivery follow each source. Edit any unit price to use your own quote.{" "}
        <button className="link" disabled={prices?.refreshing} onClick={onRefresh}>{prices?.refreshing ? "Fetching live prices…" : "Fetch prices again"}</button>
      </p>
    </div>
  );
}
