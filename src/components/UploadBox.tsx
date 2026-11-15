import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, drawingPath } from "../api";
import type { DrawingCard } from "../api";

export default function UploadBox() {
  const nav = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const [recent, setRecent] = useState<DrawingCard[]>([]);
  useEffect(() => { api.uploads().then((r) => setRecent(r.drawings.slice(0, 4))).catch(() => {}); }, []);

  async function send(f: File | undefined) {
    if (!f || busy) return;
    setErr(null);
    setBusy(f.name);
    try {
      nav(drawingPath((await api.upload(f)).id));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setBusy(null);
    }
  }

  return (
    <section className="upload">
      <button type="button" className={"dropzone" + (drag ? " drag" : "")} disabled={!!busy}
        onClick={() => input.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files[0]); }}>
        {busy ? (
          <>
            <span className="spinner" />
            <strong>Reading {busy}</strong>
            <span>Detecting doors, windows, fixtures and rooms. This takes 10–40 seconds.</span>
          </>
        ) : (
          <>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V5m0 0-4 4m4-4 4 4M5 19h14" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
            <strong>Upload your own drawing</strong>
            <span>Drop a file here or click to choose one. PNG, JPG, TIFF or PDF (first page), up to 40 MB.</span>
          </>
        )}
      </button>
      <input ref={input} type="file" accept=".png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp,.pdf" hidden onChange={(e) => send(e.target.files?.[0])} />
      {err && <p className="upload-error" role="alert">{err}</p>}
      {recent.length > 0 && (
        <p className="upload-recent">
          Recent uploads{recent.map((d) => <Link key={d.id} to={drawingPath(d.id)}>{d.title}</Link>)}
        </p>
      )}
    </section>
  );
}
