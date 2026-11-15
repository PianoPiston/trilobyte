import { useCallback, useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react";
import type { CSSProperties, MouseEvent, PointerEvent, ReactNode } from "react";
import { unionBox } from "../api";
import type { Evidence, LayerItem, Shape, Word } from "../api";

type View = { x: number; y: number; k: number };
export type ViewerHandle = { focus: (box: number[] | null) => void };

type Props = {
  src: string;
  size: [number, number];
  evidence: Evidence[];
  layer: LayerItem[] | null;
  words: Word[] | null;
  hoverId: string | null;
  selectedId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
  children?: ReactNode;
};

const KIND_COLOR: Record<string, string> = {
  unit: "#6250d6", room: "#1f4fd1", space: "#1f4fd1", door: "#d6336c", window: "#0d9bb5", toilet: "#7a8b00",
  washbasin: "#7a8b00", bathtub: "#7a8b00", shower: "#7a8b00", wall: "#7a7a7a", slab: "#9a9a9a", stair: "#2b8a3e",
};

function ShapeEl({ e, cls, color }: { e: Shape; cls: string; color?: string }) {
  const style = color ? ({ "--c": color } as CSSProperties) : undefined;
  if (e.polygon) return <polygon className={cls} style={style} points={e.polygon.map((p) => p.join(",")).join(" ")} vectorEffect="non-scaling-stroke" />;
  if (!e.bbox) return null;
  const [x0, y0, x1, y1] = e.bbox;
  return <rect className={cls} style={style} x={x0} y={y0} width={Math.max(1, x1 - x0)} height={Math.max(1, y1 - y0)} vectorEffect="non-scaling-stroke" />;
}

const clampK = (k: number) => Math.min(Math.max(k, 0.02), 12);
// Zoom to scale k while keeping the point (mx, my) of the viewport fixed
const zoomAt = (v: View, k: number, mx: number, my: number): View => ({ k, x: mx - ((mx - v.x) * k) / v.k, y: my - ((my - v.y) * k) / v.k });

const Viewer = forwardRef<ViewerHandle, Props>(function Viewer(p, ref) {
  const wrap = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<View>({ x: 0, y: 0, k: 0.1 });
  const [anim, setAnim] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const [W, H] = p.size;

  const animate = () => { setAnim(true); window.setTimeout(() => setAnim(false), 400); };
  const fitBox = useCallback((b: number[], pad: number, maxK: number) => {
    const el = wrap.current;
    if (!el) return;
    const cw = el.clientWidth, ch = el.clientHeight;
    const k = Math.min((cw * (1 - 2 * pad)) / Math.max(b[2] - b[0], 20), (ch * (1 - 2 * pad)) / Math.max(b[3] - b[1], 20), maxK);
    animate();
    setView({ k, x: cw / 2 - ((b[0] + b[2]) / 2) * k, y: ch / 2 - ((b[1] + b[3]) / 2) * k });
  }, []);
  const fit = useCallback(() => fitBox([0, 0, W, H], 0.04, 100), [W, H, fitBox]);
  // Zoom to a region; a region spanning most of the sheet shows the whole sheet instead of cropping it
  const focus = useCallback((b: number[] | null) => {
    if (b && b[2] - b[0] < W / 2 && b[3] - b[1] < H / 2) fitBox(b, 0.18, 3);
    else fit();
  }, [W, H, fitBox, fit]);
  useImperativeHandle(ref, () => ({ focus }), [focus]);

  useEffect(() => { setLoaded(false); }, [p.src]);
  useEffect(() => {
    const el = wrap.current!;
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [fit]);

  // React attaches wheel listeners as passive, so preventDefault needs a native listener
  useEffect(() => {
    const el = wrap.current!;
    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      const r = el.getBoundingClientRect();
      setView((v) => zoomAt(v, clampK(v.k * Math.exp(-ev.deltaY * 0.0015)), ev.clientX - r.left, ev.clientY - r.top));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const zoom = (f: number) => {
    const el = wrap.current!;
    animate();
    setView((v) => zoomAt(v, clampK(v.k * f), el.clientWidth / 2, el.clientHeight / 2));
  };

  const onDown = (e: PointerEvent) => { drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false }; };
  const onMove = (e: PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
    setView((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }));
  };
  const onUp = () => { window.setTimeout(() => { drag.current = null; }); };

  const label = (text: string) => (e: MouseEvent) => {
    const r = wrap.current!.getBoundingClientRect();
    setTip({ x: e.clientX - r.left + 14, y: e.clientY - r.top + 14, text });
  };
  const noTip = () => setTip(null);

  const evIds = new Set(p.evidence.map((e) => e.id));
  const placed = p.evidence.filter((e) => e.polygon || e.bbox);
  const stop = (e: PointerEvent) => e.stopPropagation();

  return (
    <div className="viewer" ref={wrap} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={() => { drag.current = null; noTip(); }}>
      <div className={"stage" + (anim ? " anim" : "")} style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})`, width: W, height: H }}>
        <img ref={(el) => { if (el?.complete && el.naturalWidth) setLoaded(true); }} src={p.src} width={W} height={H} draggable={false} onLoad={() => setLoaded(true)} alt="Drawing sheet" />
        <svg className="overlay" width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
          {p.layer?.filter((l) => !evIds.has(l.id)).map((l) => (
            <g key={"l" + l.id} onMouseMove={label(l.label)} onMouseLeave={noTip}>
              <ShapeEl e={l} cls={"lay lay-" + l.kind} color={KIND_COLOR[l.kind] || "#888"} />
            </g>
          ))}
          {p.words?.map((w, i) => (
            <g key={"w" + i} onMouseMove={label(`“${w.text}”${w.conf != null && w.conf < 1 ? ` · OCR ${Math.round(w.conf * 100)}%` : ""}`)} onMouseLeave={noTip}>
              <ShapeEl e={w} cls="word" />
            </g>
          ))}
          {placed.map((e, i) => (
            <g key={"e" + e.id + i}
              onMouseEnter={() => p.onHover(e.id)} onMouseLeave={() => { p.onHover(null); noTip(); }}
              onMouseMove={label(e.label + (e.element_id && e.element_id !== e.label ? ` · ${e.element_id}` : ""))}
              onClick={() => { if (!drag.current?.moved) p.onSelect(e.id === p.selectedId ? null : e.id); }}>
              <ShapeEl e={e} cls={"ev" + (e.approximate ? " approx" : "") + (p.hoverId === e.id || p.selectedId === e.id ? " on" : "")} />
            </g>
          ))}
        </svg>
      </div>
      {!loaded && <div className="viewer-loading">Loading drawing…</div>}
      {tip && <div className="tip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
      <div className="viewer-layers" onPointerDown={stop}>{p.children}</div>
      <div className="viewer-tools" onPointerDown={stop}>
        {placed.length > 0 && <button onClick={() => focus(unionBox(placed))}>Show evidence</button>}
        <button onClick={() => zoom(1 / 1.4)} aria-label="Zoom out">−</button>
        <span>{Math.round(view.k * 100)}%</span>
        <button onClick={() => zoom(1.4)} aria-label="Zoom in">+</button>
        <button onClick={fit}>Fit</button>
      </div>
    </div>
  );
});

export default Viewer;
