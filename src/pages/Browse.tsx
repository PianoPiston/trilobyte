import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, drawingPath } from "../api";
import type { DrawingCard, SourceInfo } from "../api";
import UploadBox from "../components/UploadBox";

const TRACKS = [["all", "All"], ["modern", "CAD, BIM and plans"], ["historic", "Historic archives"]];

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
          <h1>Ask questions about construction drawings</h1>
          <p>Each answer marks the rooms, openings and symbols it was computed from on the sheet, and states its method, confidence and inference cost.</p>
        </div>
        <UploadBox />
      </section>

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
      {items && (
        <p className="count">
          {shown.length} drawings{shown.every((d) => d.seen_in_training === false) && ", none of them used in training"}
        </p>
      )}
      <div className="grid">
        {shown.map((d) => (
          <Link key={d.id} to={drawingPath(d.id)} className="card">
            <div className="thumb"><img src={d.thumb_url} loading="lazy" alt="" /></div>
            <h2 title={d.title}>{d.title}</h2>
            <p className="card-meta">{d.source_label} · {d.formats.join(", ")}</p>
            {d.teaser?.[0] && <p className="teaser">{d.teaser[0]}</p>}
            <p className="card-credit" title={d.credit || ""}>{d.licence} · {d.credit}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
