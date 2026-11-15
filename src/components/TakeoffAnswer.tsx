import { UNIT, eur, fmt, materialLines, roomArea, roomName, totals } from "../lib/takeoff";
import type { Assumptions, Prices, Takeoff } from "../lib/takeoff";
import type { Intent } from "../lib/intent";

const host = (u: string) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; } };

// Answer to a material or cost question, computed from the measured rooms and the live unit prices
export default function TakeoffAnswer({ intent, takeoff, m, a, prices, onMaterials }: {
  intent: Intent; takeoff: Takeoff; m: number; a: Assumptions; prices: Prices | null; onMaterials: () => void;
}) {
  const x = totals(takeoff, m, a, intent.rooms);
  const lines = materialLines(x, takeoff, m, a, intent.rooms === null);
  const price = (k: string) => prices?.items.find((p) => p.key === k);
  const shown = intent.material ? lines.filter((l) => l.key === intent.material) : lines;
  const main = shown[0];
  const total = shown.reduce((s, l) => s + l.qty * (price(l.key)?.price ?? 0), 0);
  const p = price(main.key);
  const exact = takeoff.source !== "segmented";
  return (
    <div className={"answer-card " + (exact ? "st-ok" : "st-check")}>
      <div className="answer-top">
        <span className="verdict">{exact ? "Computed from the CAD/BIM geometry" : "Computed from the measured plan"}</span>
        <span className="method">Quantity takeoff</span>
      </div>
      {intent.material ? (
        <div className="answer-value"><span className="v">{fmt(main.qty)}</span><span className="u">{UNIT[main.unit]} {main.label.split(",")[0].toLowerCase()}</span></div>
      ) : (
        <div className="answer-value"><span className="v">{eur(total)}</span><span className="u">for {shown.length} materials</span></div>
      )}
      <p className="answer-note">
        For {intent.scope}{intent.material && <>, costing <b>{eur(main.qty * (p?.price ?? 0))}</b> at {eur(p?.price ?? 0)} per {UNIT[main.unit]} ({p?.live ? "live web price" : "reference price"})</>}.
      </p>
      {!exact && <ul className="reasons"><li>Room areas come from walls found in the image and a scale estimated as: {takeoff.scale.method}. Check the scale before ordering.</li></ul>}
      <dl className="facts">
        {shown.map((l) => [
          <dt key={l.key + "k"}>{intent.material ? "Quantity" : l.label}</dt>,
          <dd key={l.key + "v"}>{intent.material ? l.basis : `${fmt(l.qty)} ${UNIT[l.unit]} · ${eur(l.qty * (price(l.key)?.price ?? 0))}`}</dd>,
        ])}
        <dt>Rooms</dt>
        <dd>{x.rooms.length > 4 ? `${x.rooms.length} rooms, ${fmt(x.floor)} m²` : x.rooms.map((r) => `${roomName(r)} ${fmt(roomArea(r, m))} m²`).join(", ")}</dd>
      </dl>
      {intent.material && p?.live && p.sources && (
        <div className="sources">
          {p.sources.slice(0, 2).map((s, i) => <a key={i} href={s.url} target="_blank" rel="noreferrer noopener">{eur(s.price)} per {UNIT[main.unit]} · {host(s.url)} ↗</a>)}
        </div>
      )}
      <button className="link" onClick={onMaterials}>Change slab thickness, waste or prices in Materials →</button>
    </div>
  );
}
