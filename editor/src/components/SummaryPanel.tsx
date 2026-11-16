import { eur, fmt, measuredArea, roomArea, roomName, roomPerimeter } from "../lib/takeoff";
import type { Room, Takeoff, Totals } from "../lib/takeoff";

const SOURCE: Record<Takeoff["source"], string> = {
  cad: "Rooms and areas are exact, computed from the CAD file.",
  bim: "Room areas are exact, read from the BIM model. Room outlines on the sheet are bounding boxes.",
  segmented: "Estimated from the image. Spaces are the regions enclosed by walls, so stairwells, porches and closets count as spaces, and a wall drawn as a thin line can be missed, which merges two rooms. Doors and windows come from the symbol detector. Areas printed on the drawing (marked P) are used where present. Check the outlines on the plan.",
};

export default function SummaryPanel({ takeoff, m, x, room, concrete, onRoom, onAsk, onMaterials }: {
  takeoff: Takeoff; m: number | null; x: Totals | null; room: Room | null;
  concrete: { qty: number; cost: number } | null; onRoom: (id: string | null) => void; onAsk: (q: string) => void; onMaterials: () => void;
}) {
  if (!m || !x) {
    return (
      <div className="pane">
        <p>This drawing has no known scale yet. Pick <b>Set scale</b> in the toolbar and click the two ends of a length you know, such as a door opening or a dimensioned wall.</p>
        <p className="muted">{takeoff.rooms.length} rooms, {takeoff.doors.length} doors and {takeoff.windows.length} windows were found.</p>
      </div>
    );
  }
  const name = room ? roomName(room) : null;
  const figures: [string, string, string][] = room
    ? [["Floor area", fmt(x.floor), "m²"], ["Perimeter", fmt(x.perimeter), "m"], ["Wall faces", fmt(x.wallArea), "m²"]]
    : [["Floor area", fmt(x.floor), "m²"], [takeoff.source === "segmented" ? "Enclosed spaces" : "Rooms", String(x.rooms.length), ""], ["Doors", String(x.doors), ""],
       ["Windows", String(x.windows), ""], ["Room perimeters", fmt(x.perimeter), "m"], ["Wall faces", fmt(x.wallArea), "m²"]];
  const questions = room
    ? [`How much concrete do I need for ${name}?`, `How much does laminate flooring for ${name} cost?`, `How much paint do I need for ${name}?`, `What is the area of ${name}?`]
    : ["How much concrete do I need for this floor?", "What do the materials for this floor cost?", "How many rooms are on this floor?", "What is the total floor area?", "How many doors are shown on this floor plan?"];
  return (
    <div className="summary">
      {room && (
        <div className="scope">
          <span>{name}</span>
          <button className="link" onClick={() => onRoom(null)}>Show whole floor</button>
        </div>
      )}
      <div className="figures">
        {figures.map(([k, v, u]) => <div key={k}><span>{k}</span><b>{v}<i>{u}</i></b></div>)}
        {concrete && (
          <button className="figure-cta" onClick={onMaterials}>
            <span>Concrete for the slab</span><b>{fmt(concrete.qty)}<i>m³</i></b><em>{eur(concrete.cost)} · see all materials →</em>
          </button>
        )}
      </div>
      <p className="fineprint">{SOURCE[takeoff.source]}</p>

      <h3>Ask about {room ? name : "this floor"}</h3>
      <div className="examples">{questions.map((q) => <button key={q} onClick={() => onAsk(q)}>{q}</button>)}</div>

      {!room && takeoff.rooms.length > 0 && (
        <>
          <h3>Rooms</h3>
          <table className="rooms">
            <thead><tr><th>Room</th><th className="num">Area m²</th><th className="num">Perimeter m</th></tr></thead>
            <tbody>{[...takeoff.rooms].sort((p, q) => roomArea(q, m) - roomArea(p, m)).map((r) => (
              <tr key={r.id} onClick={() => onRoom(r.id)}>
                <td>{roomName(r)}{r.outdoor && <span className="muted"> outdoor</span>}{r.shaft && <span className="muted"> shaft</span>}</td>
                <td className="num" title={r.printed_area_m2 ? `Printed on the drawing; measured ${fmt(measuredArea(r, m), 2)} m²` : undefined}>
                  {fmt(roomArea(r, m), 2)}{r.printed_area_m2 != null && <sup>P</sup>}</td><td className="num">{fmt(roomPerimeter(r, m))}</td>
              </tr>
            ))}</tbody>
          </table>
        </>
      )}
    </div>
  );
}
