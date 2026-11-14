import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { DrawingCard } from "../api";

const ACCEPT = ".png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp,.pdf";

export default function UploadBox() {
  const nav = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const [recent, setRecent] = useState<DrawingCard[]>([]);
  useEffect(() => { api.uploads().then((r) => setRecent(r.drawings.slice(0, 6))).catch(() => {}); }, []);

  async function send(f: File | undefined) {
    if (!f || busy) return;
    setErr(null);
    setBusy(`Uploading ${f.name} and detecting doors, windows, fixtures and rooms…`);
    try {
      const d = await api.upload(f);
      nav(`/d/${encodeURIComponent(d.id)}`);
    } catch (e: any) {
      const m = String(e?.message || e);
      const detail = m.match(/"detail":"([^"]+)"/);
      setErr(detail ? detail[1] : m);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className={"upload" + (drag ? " drag" : "")}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files?.[0]); }}>
      <div className="upload-main">
        <div>
          <h2>Ask about your own drawing</h2>
          <p className="muted">Drop a floor plan or drawing sheet (PNG, JPG, TIFF or PDF, first page, max 40 MB). The symbol detector reads it once
            (about 10–20 s), then ask anything in English or Finnish.</p>
        </div>
        <button className="btn primary" disabled={!!busy} onClick={() => input.current?.click()}>{busy ? "Analyzing…" : "Upload drawing"}</button>
        <input ref={input} type="file" accept={ACCEPT} hidden onChange={(e) => send(e.target.files?.[0])} />
      </div>
      {busy && <div className="upload-status"><span className="spinner" /> {busy}</div>}
      {err && <div className="upload-error">⚠ {err}</div>}
      {recent.length > 0 && (
        <div className="upload-recent small">
          <span className="muted">Recent uploads:</span>
          {recent.map((d) => <Link key={d.id} to={`/d/${encodeURIComponent(d.id)}`}>{d.title}</Link>)}
        </div>
      )}
    </section>
  );
}
