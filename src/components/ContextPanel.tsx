import type { Context } from "../api";

const FIELDS: [string, string][] = [
  ["building", "Building"], ["place", "Place"], ["country", "Country"], ["year", "Year"], ["architect_or_author", "Architect / author"],
  ["drawing_type", "Drawing type"], ["floor", "Floor"], ["scale", "Scale"], ["language", "Label language"], ["permit_authority", "Authority"],
  ["subjects", "Subjects"],
];

function show(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v !== "object") return String(v);
  if (Array.isArray(v)) return v.map((x) => (x && typeof x === "object" ? x.phrase || x.level || x.term || JSON.stringify(x) : String(x))).join(", ");
  const o = v as any;
  return o.text || o.name || o.years?.join(", ") || JSON.stringify(o);
}

function host(u: string) {
  try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; }
}

export default function ContextPanel({ c }: { c: Context }) {
  const f = c.fields || {};
  const terms = (f.key_terms?.value as { term: string; en: string }[]) || [];
  return (
    <div className="pane">
      {c.summary?.value && <p className="ctx-summary">{c.summary.value}</p>}
      <dl className="kv">
        {FIELDS.filter(([k]) => f[k] && show(f[k].value)).map(([k, label]) => (
          <div key={k}>
            <dt>{label}</dt>
            <dd>
              {show(f[k].value)}
              {(f[k].src || []).filter((u) => u.startsWith("http")).slice(0, 2).map((u) => (
                <a key={u} className="src" href={u} target="_blank" rel="noreferrer noopener" title={f[k].from}>{host(u)} ↗</a>
              ))}
            </dd>
          </div>
        ))}
      </dl>
      {terms.length > 0 && (
        <>
          <h3>Terms on the sheet</h3>
          <p className="terms">{terms.slice(0, 12).map((t, i) => <span key={i}>{t.term} <i>{t.en}</i></span>)}</p>
        </>
      )}
      {c.web && c.web.length > 0 && (
        <>
          <h3>Web results <span>· hints that may describe a similar building</span></h3>
          <ul className="web">{c.web.slice(0, 4).map((w, i) => (
            <li key={i}><a href={w.url} target="_blank" rel="noreferrer noopener">{w.title || host(w.url)} ↗</a><p>{w.snippet?.slice(0, 220)}</p></li>
          ))}</ul>
        </>
      )}
      {c.licence?.source_url && <a href={c.licence.source_url} target="_blank" rel="noreferrer noopener">Open the archive record ↗</a>}
    </div>
  );
}
