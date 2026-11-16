import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, drawingPath } from "../api";

const EXAMPLES = ["3 bedrooms and a sauna", "kolme makuuhuonetta ja sauna", "at least 2 bathrooms and a balcony", "4 apartments",
  "no sauna 2 bedrooms", "Helsinki 1909", "lighthouse", "church floor plan"];
const KEYS: Record<string, string> = { showers_baths: "showers and baths", wc_rooms: "WC rooms" };
const keyLabel = (k: string) => KEYS[k] || k;

export default function Search() {
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") || "");
  const [r, setR] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const run = (query: string) => {
    setQ(query);
    setSp(query ? { q: query } : {});
    if (!query.trim()) return setR(null);
    setBusy(true);
    api.search(query).then(setR).finally(() => setBusy(false));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (q) run(q); }, []);

  return (
    <div className="page narrow">
      <h1>Search drawings by their contents</h1>
      <p className="lead">The index holds the system's own answers for the held-out test drawings, exact CAD facts for the Swiss floors and the archive context of the historic drawings.</p>
      <form className="ask" onSubmit={(e) => { e.preventDefault(); run(q); }}>
        <div className="ask-row">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="3 bedrooms and a sauna" aria-label="Search" autoFocus />
          <button type="submit" disabled={busy}>Search</button>
        </div>
        <div className="examples">{EXAMPLES.map((e) => <button type="button" key={e} onClick={() => run(e)}>{e}</button>)}</div>
      </form>
      {r && (
        <>
          <p className="count">
            {r.total} drawing{r.total === 1 ? "" : "s"}
            {r.parsed.constraints.map((c: any, i: number) => <span key={i} className="chip on">{keyLabel(c.key)} {c.op === "=" ? "=" : "≥"} {c.value}</span>)}
            {r.parsed.words.map((w: string) => <span key={w} className="chip on">{w}</span>)}
          </p>
          <div className="results">
            {r.results.map((x: any) => (
              <Link key={x.id} className="result" to={drawingPath(x.id)}>
                <img src={x.thumb_url} loading="lazy" alt="" />
                <div>
                  <h2>{x.title}</h2>
                  <p className="card-meta">{x.source}</p>
                  <p className="facts-line">
                    {x.matched.length > 0
                      ? x.matched.map((m: any) => (
                        <span key={m.key} className={m.uncertain ? "uncertain" : ""} title={`${m.method}, confidence ${m.confidence}`}>
                          {keyLabel(m.key)}: {m.value}{m.uncertain && " (uncertain)"}
                        </span>))
                      : Object.entries<any>(x.facts).slice(0, 5).map(([k, f]) => <span key={k}>{keyLabel(k)}: {f.value}</span>)}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
