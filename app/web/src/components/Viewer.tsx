import { useCallback, useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react";
import type { Evidence, LayerItem } from "../api";

type View = { x: number; y: number; k: number };
export type ViewerHandle = { focus: (box: number[] | null) => void; fit: () => void };

type Props = {
  src: string;
  size: [number, number];
  evidence: Evidence[];
  layer: LayerItem[] | null;
  showLayer: boolean;
  hoverId: string | null;
  selectedId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
};

export function boxOf(e: { polygon?: number[][]; bbox?: number[] }): number[] | null {
  if (e.bbox) return e.bbox;
  if (e.polygon && e.polygon.length) {
    const xs = e.polygon.map((p) => p[0]), ys = e.polygon.map((p) => p[1]);
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  return null;
}

const KIND_COLOR: Record<string, string> = {
  unit: "#6250d6", room: "#2a78d6", space: "#2a78d6", door: "#e34948", window: "#0d9bb5", toilet: "#eb6834",
  washbasin: "#eb6834", bathtub: "#eb6834", shower: "#eb6834", wall: "#7a7a7a", slab: "#9a9a9a", stair: "#008300",
};

function Shape({ e, cls, color }: { e: { polygon?: number[][]; bbox?: number[] }; cls: string; color?: string }) {
  const style = color ? ({ ["--c" as any]: color } as React.CSSProperties) : undefined;
  if (e.polygon) return <polygon className={cls} style={style} points={e.polygon.map((p) => p.join(",")).join(" ")} vectorEffect="non-scaling-stroke" />;
  if (e.bbox) {
    const [x0, y0, x1, y1] = e.bbox;
    return <rect className={cls} style={style} x={x0} y={y0} width={Math.max(1, x1 - x0)} height={Math.max(1, y1 - y0)} vectorEffect="non-scaling-stroke" />;
  }
  return null;
}

const Viewer = forwardRef<ViewerHandle, Props>(function Viewer(p, ref) {
  const wrap = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<View>({ x: 0, y: 0, k: 0.1 });
  const [anim, setAnim] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const [W, H] = p.size;

  const fitBox = useCallback((b: number[], pad = 0.08, maxK = 4) => {
    const el = wrap.current;
    if (!el) return;
    const cw = el.clientWidth, ch = el.clientHeight;
    const bw = Math.max(b[2] - b[0], 20), bh = Math.max(b[3] - b[1], 20);
    const k = Math.min((cw * (1 - 2 * pad)) / bw, (ch * (1 - 2 * pad)) / bh, maxK);
    setAnim(true);
    setView({ k, x: cw / 2 - ((b[0] + b[2]) / 2) * k, y: ch / 2 - ((b[1] + b[3]) / 2) * k });
    window.setTimeout(() => setAnim(false), 420);
  }, []);
  const fit = useCallback(() => fitBox([0, 0, W, H], 0.02, 100), [W, H, fitBox]);

  useImperativeHandle(ref, () => ({
    focus: (b) => (b ? fitBox(b, 0.18, 3) : fit()),
    fit,
  }), [fitBox, fit]);

  useEffect(() => { setLoaded(false); }, [p.src]);
  useEffect(() => { fit(); }, [W, H, fit]);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => fit());
    ro.observe(el);
    return () => ro.disconnect();
  }, [fit]);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      const r = el.getBoundingClientRect();
      const mx = ev.clientX - r.left, my = ev.clientY - r.top;
      setView((v) => {
        const f = Math.exp(-ev.deltaY * 0.0015);
        const k = Math.min(Math.max(v.k * f, 0.02), 12);
        return { k, x: mx - ((mx - v.x) * k) / v.k, y: my - ((my - v.y) * k) / v.k };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const zoom = (f: number) => {
    const el = wrap.current!;
    const mx = el.clientWidth / 2, my = el.clientHeight / 2;
    setAnim(true);
    setView((v) => {
      const k = Math.min(Math.max(v.k * f, 0.02), 12);
      return { k, x: mx - ((mx - v.x) * k) / v.k, y: my - ((my - v.y) * k) / v.k };
    });
    window.setTimeout(() => setAnim(false), 250);
  };

  const onDown = (e: React.PointerEvent) => {
    drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false };
    (e.target as Element).setPointerCapture?.(e.pointerId);
  };
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (d) {
      const dx = e.clientX - d.x, dy = e.clientY - d.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
      setView((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }));
    }
  };
  const onUp = () => { drag.current = null; };

  const label = (text: string) => (e: React.MouseEvent) => {
    const r = wrap.current!.getBoundingClientRect();
    setTip({ x: e.clientX - r.left + 14, y: e.clientY - r.top + 12, text });
  };

  const evIds = new Set(p.evidence.map((e) => e.id));
  const placed = p.evidence.filter((e) => e.polygon || e.bbox);

  return (
    <div className="viewer" ref={wrap} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={() => { onUp(); setTip(null); }}>
      <div className={"stage" + (anim ? " anim" : "")} style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})`, width: W, height: H }}>
        <img ref={(el) => { if (el && el.complete && el.naturalWidth) setLoaded(true); }} src={p.src} width={W} height={H} draggable={false} onLoad={() => setLoaded(true)} alt="drawing" />
        <svg className="overlay" width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
          {p.showLayer && p.layer?.filter((l) => !evIds.has(l.id)).map((l) => (
            <g key={"l" + l.id} onMouseMove={label(l.label)} onMouseLeave={() => setTip(null)}>
              <Shape e={l} cls={"lay lay-" + l.kind} color={KIND_COLOR[l.kind] || "#888"} />
            </g>
          ))}
          {placed.map((e, i) => {
            const on = p.hoverId === e.id || p.selectedId === e.id;
            return (
              <g key={"e" + e.id + i}
                onMouseEnter={() => p.onHover(e.id)} onMouseLeave={() => { p.onHover(null); setTip(null); }}
                onMouseMove={label(e.label + (e.element_id && e.element_id !== e.label ? `  ·  ${e.element_id}` : ""))}
                onClick={(ev) => { if (!drag.current?.moved) { ev.stopPropagation(); p.onSelect(e.id === p.selectedId ? null : e.id); } }}>
                <Shape e={e} cls={"ev" + (e.approximate ? " approx" : "") + (on ? " on" : "")} />
              </g>
            );
          })}
        </svg>
      </div>
      {!loaded && <div className="viewer-loading">Loading drawing…</div>}
      {tip && <div className="tip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
      <div className="viewer-tools" onPointerDown={(e) => e.stopPropagation()}>
        <button onClick={() => zoom(1.4)} title="Zoom in">＋</button>
        <button onClick={() => zoom(1 / 1.4)} title="Zoom out">－</button>
        <button onClick={fit} title="Fit drawing">⤢</button>
        {placed.length > 0 && <button onClick={() => {
          const bs = placed.map(boxOf).filter(Boolean) as number[][];
          fitBox([Math.min(...bs.map((b) => b[0])), Math.min(...bs.map((b) => b[1])), Math.max(...bs.map((b) => b[2])), Math.max(...bs.map((b) => b[3]))], 0.1, 3);
        }} title="Zoom to evidence">◎</button>}
      </div>
      <div className="viewer-zoom">{Math.round(view.k * 100)}%</div>
    </div>
  );
});

export default Viewer;
