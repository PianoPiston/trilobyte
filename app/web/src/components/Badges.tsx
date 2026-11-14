import type { DrawingCard } from "../api";

export function DrawingBadges({ d }: { d: DrawingCard }) {
  return (
    <div className="badges">
      <span className={"badge src s-" + d.track}>{d.source_label}</span>
      {d.formats.map((f) => <span key={f} className={"badge fmt" + (f === "DXF" || f === "IFC" ? " fmt-exact" : "")}>{f}</span>)}
      {d.seen_in_training === false && <span className="badge unseen" title={`${d.split} split: this drawing was never used for training`}>Not seen in training</span>}
      {d.seen_in_training === true && <span className="badge seen">training drawing</span>}
      {d.has_context && <span className="badge ctx">context file</span>}
    </div>
  );
}

export function CreditLine({ d }: { d: DrawingCard }) {
  return (
    <div className="credit" title={d.credit || ""}>
      <span className="lic">{d.licence}</span> {d.credit}
      {d.source_url && <> · <a href={d.source_url} target="_blank" rel="noreferrer noopener">source</a></>}
      {d.licence?.includes("NC") && <span className="muted"> · non-commercial use only</span>}
    </div>
  );
}
