import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, drawingPath } from "../api";
import type { DrawingCard, SourceInfo } from "../api";
import UploadBox from "../components/UploadBox";

const TRACKS = [["all", "All"], ["modern", "CAD, BIM and plans"], ["historic", "Historic archives"]];
const STEPS = [
  ["Measured", "Rooms, areas and perimeters are read from the CAD or BIM file, or found from the walls of a scanned plan. Distance and area tools measure anything else."],
  ["Priced", "Concrete, flooring, plasterboard, paint and skirting quantities for a room or the whole floor, with unit prices fetched live from the web."],
  ["Answered", "Questions in plain language. Each answer marks its evidence on the sheet and states its method and confidence."],
  ["In 3D", "Every plan becomes a model you can orbit, with walls raised from the drawing itself."],
];

export default function Browse() {
  const [items, setItems] = useState<DrawingCard[] | null>(null);
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [track, setTrack] = useState("all");
  const [source, setSource] = useState("all");
  useEffect(() => { api.drawings().then((r) => { setItems(r.drawings); setSources(r.sources); }); }, []);
  const shown = (items || []).filter((d) => (track === "all" || d.track === track) && (source === "all" || d.source === source));

  return (
    <div className="page">
      <section className="intro">
        <div>
          <h1>Measure and price any floor plan.</h1>
          <p>Drop in a drawing. Trilobyte finds the rooms, measures them, works out how much concrete and finishing material the floor needs at today's prices, and answers questions with the evidence marked on the sheet.</p>
        </div>
        <UploadBox />
      </section>

      <dl className="steps">
        {STEPS.map(([k, text]) => <div key={k}><dt>{k}</dt><dd>{text}</dd></div>)}
      </dl>

      <h2 className="section">Drawings to try</h2>
      <div className="filters">
        <div className="seg">
          {TRACKS.map(([k, label]) =>
            <button key={k} className={track === k ? "on" : ""} onClick={() => { setTrack(k); setSource("all"); }}>{label}</button>)}
        </div>
        <div className="chips">
          {sources.filter((s) => track === "all" || s.track === track).map((s) => (
            <button key={s.source} className={"chip" + (source === s.source ? " on" : "")}
              onClick={() => setSource(source === s.source ? "all" : s.source)}>{s.label} <span>{s.n}</span></button>
          ))}
        </div>
      </div>

      {!items && <div className="loading">Loading drawings…</div>}
      <div className="grid">
        {shown.map((d) => (
          <Link key={d.id} to={drawingPath(d.id)} className="card">
            <div className="thumb"><img src={d.thumb_url} loading="lazy" alt="" /></div>
            <h3 title={d.title}>{d.title}</h3>
            <p className="card-meta">{d.source_label} · {d.formats.join(", ")}</p>
            <p className="card-credit" title={d.credit || ""}>{d.licence} · {d.credit}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
