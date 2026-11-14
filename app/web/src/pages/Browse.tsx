import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { DrawingCard } from "../api";
import { DrawingBadges } from "../components/Badges";
import UploadBox from "../components/UploadBox";

export default function Browse() {
  const [items, setItems] = useState<DrawingCard[]>([]);
  const [sources, setSources] = useState<{ source: string; label: string; track: string; n: number }[]>([]);
  const [track, setTrack] = useState<string>("all");
  const [source, setSource] = useState<string>("all");
  const [unseen, setUnseen] = useState(false);
  useEffect(() => { api.drawings().then((r) => { setItems(r.drawings); setSources(r.sources); }); }, []);
  const shown = useMemo(() => items.filter((d) =>
    (track === "all" || d.track === track) && (source === "all" || d.source === source) && (!unseen || d.seen_in_training === false)), [items, track, source, unseen]);
  return (
    <div className="page">
      <section className="hero">
        <h1>Make blueprints talk.</h1>
        <p>Modern drawings become <b>standardized data</b>. Historic drawings get their <b>context</b> back. Every answer points to its <b>evidence</b>, so a site engineer can check it in seconds.</p>
      </section>
      <UploadBox />
      <div className="filters">
        <div className="seg">
          {[["all", "All"], ["modern", "Modern (CAD · BIM · plans)"], ["historic", "Historic archives"]].map(([k, l]) =>
            <button key={k} className={track === k ? "on" : ""} onClick={() => { setTrack(k); setSource("all"); }}>{l}</button>)}
        </div>
        <div className="chips">
          <button className={"chip" + (source === "all" ? " on" : "")} onClick={() => setSource("all")}>All sources</button>
          {sources.filter((s) => track === "all" || s.track === track).map((s) => (
            <button key={s.source} className={"chip" + (source === s.source ? " on" : "")} onClick={() => setSource(s.source)}>{s.label} <span className="muted">{s.n}</span></button>
          ))}
        </div>
        <label className="toggle"><input type="checkbox" checked={unseen} onChange={(e) => setUnseen(e.target.checked)} /> Only drawings not seen in training</label>
      </div>
      <div className="grid">
        {shown.map((d) => (
          <Link key={d.id} to={`/d/${encodeURIComponent(d.id)}`} className="card">
            <div className="thumb"><img src={d.thumb_url} alt="" /></div>
            <div className="card-body">
              <div className="card-title" title={d.title}>{d.title}</div>
              <div className="muted small">{d.subtitle}</div>
              <DrawingBadges d={d} />
              {d.teaser && d.teaser[0] && <div className="teaser">“{d.teaser[0]}”</div>}
              <div className="card-credit" title={d.credit || ""}>{d.licence} · {d.credit}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
