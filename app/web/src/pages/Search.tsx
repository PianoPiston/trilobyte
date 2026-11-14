import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";

const EXAMPLES = ["3 bedrooms and a sauna", "kolme makuuhuonetta ja sauna", "at least 2 bathrooms and a balcony", "4 apartments",
  "no sauna 2 bedrooms", "Helsinki 1909", "lighthouse", "church floor plan"];
const KEY_LABEL: Record<string, string> = { bedrooms: "bedrooms", saunas: "saunas", toilets: "toilets", bathrooms: "bathrooms", kitchens: "kitchens",
  balconies: "balconies", windows: "windows", doors: "doors", apartments: "apartments", floors: "floors", showers_baths: "showers+baths" };

export default function Search() {
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") || "");
  const [r, setR] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const run = (qq: string) => {
    setQ(qq); setSp(qq ? { q: qq } : {}); if (!qq.trim()) { setR(null); return; }
    setBusy(true); api.search(qq).then(setR).finally(() => setBusy(false));
  };
  useEffect(() => { if (sp.get("q")) run(sp.get("q")!); /* eslint-disable-next-line */ }, []);
  return (
    <div className="page">
      <h1 className="page-title">Search drawings</h1>
      <p className="muted">Find drawings by what is in them. The index is built from our system's own answers on held-out test drawings (exact CAD facts for Swiss floors) plus the historic context files.</p>
      <form className="ask search-box" onSubmit={(e) => { e.preventDefault(); run(q); }}>
        <div className="ask-row"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. 3 bedrooms and a sauna" /><button type="submit">Search</button></div>
        <div className="examples">{EXAMPLES.map((e) => <button type="button" className="ex" key={e} onClick={() => run(e)}>{e}</button>)}</div>
      </form>
      {busy && <div className="loading">Searching…</div>}
      {r && (
        <>
          <div className="parsed small">
            {r.parsed.constraints.map((c: any, i: number) => <span key={i} className="chip on">{KEY_LABEL[c.key] || c.key} {c.op === "=" ? "=" : "≥"} {c.value}</span>)}
            {r.parsed.words.map((w: string) => <span key={w} className="chip">“{w}”</span>)}
            <span className="muted"> {r.total} drawing{r.total === 1 ? "" : "s"}</span>
          </div>
          <div className="results">
            {r.results.map((x: any) => (
              <Link key={x.id} className="result" to={`/d/${encodeURIComponent(x.id)}`}>
                <img src={x.thumb_url} loading="lazy" alt="" />
                <div>
                  <div className="card-title">{x.title}</div>
                  <div className="small muted">{x.source}{x.split === "test" ? " · not seen in training" : ""}{x.featured ? " · demo drawing" : ""}</div>
                  <div className="facts">
                    {x.matched.map((m: any) => <span key={m.key} className={"chip " + (m.uncertain ? "uncertain" : "on")} title={`${m.method}, confidence ${m.confidence}`}>{m.value} {KEY_LABEL[m.key] || m.key}{m.uncertain ? " ?" : ""}</span>)}
                    {x.matched.length === 0 && Object.entries(x.facts).slice(0, 5).map(([k, f]: any) => <span key={k} className="chip">{f.value} {KEY_LABEL[k] || k}</span>)}
                  </div>
                </div>
              </Link>
            ))}
          </div>
          <p className="muted small">{r.index_note}</p>
        </>
      )}
    </div>
  );
}
