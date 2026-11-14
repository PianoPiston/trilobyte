import type { Context } from "../api";

const ORDER: [string, string][] = [
  ["building", "Building"], ["place", "Place"], ["country", "Country"], ["year", "Year"], ["architect_or_author", "Architect / author"],
  ["drawing_type", "Drawing type"], ["floor", "Floor"], ["scale", "Scale"], ["language", "Label language"], ["permit_authority", "Authority"],
  ["subjects", "Subjects"],
];

function show(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "string" || typeof v === "number") return String(v);
  if (Array.isArray(v)) return v.map((x) => (typeof x === "object" && x ? (x as any).phrase || (x as any).level || (x as any).term || JSON.stringify(x) : String(x))).join(", ");
  const o = v as any;
  return o.text || o.name || (o.years ? o.years.join(", ") : JSON.stringify(o));
}

function host(u: string) {
  try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; }
}

export default function ContextPanel({ c }: { c: Context }) {
  const f = c.fields || {};
  const glossary = (f.key_terms?.value as any[]) || [];
  return (
    <div className="ctx pad">
      <p className="muted small">Context rebuilt from the archive record{c.web?.length ? " and a web search" : ""}. Every field links to where it came from. Archive text is untrusted and only given to the model as reference data.</p>
      {c.summary?.value && <p className="ctx-summary">{c.summary.value}</p>}
      <dl className="kv">
        {ORDER.filter(([k]) => f[k] && show(f[k].value)).map(([k, label]) => (
          <div key={k} className="kv-row">
            <dt>{label}</dt>
            <dd>
              {show(f[k].value)}
              {(f[k].src || []).filter((u) => u.startsWith("http")).slice(0, 2).map((u, i) => (
                <a key={i} className="src" href={u} target="_blank" rel="noreferrer noopener" title={f[k].from}>{host(u)} ↗</a>
              ))}
            </dd>
          </div>
        ))}
      </dl>
      {glossary.length > 0 && (
        <>
          <div className="muted small">Key terms on the sheet</div>
          <div className="terms">{glossary.slice(0, 12).map((t, i) => <span key={i} className="chip">{t.term} → {t.en}</span>)}</div>
        </>
      )}
      {c.web && c.web.length > 0 && (
        <>
          <div className="muted small">Web context (hints, may describe a similar building)</div>
          <ul className="web">{c.web.slice(0, 4).map((w, i) => (
            <li key={i}><a href={w.url} target="_blank" rel="noreferrer noopener">{w.title || host(w.url)} ↗</a><div className="small muted">{w.snippet?.slice(0, 220)}</div></li>
          ))}</ul>
        </>
      )}
      {c.licence?.source_url && <p className="small"><a href={c.licence.source_url} target="_blank" rel="noreferrer noopener">Open the archive record ↗</a></p>}
    </div>
  );
}
