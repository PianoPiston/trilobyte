import { useCallback, useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react";
import type { CSSProperties, MouseEvent, PointerEvent, ReactNode } from "react";
import { boxOf, unionBox } from "../api";
import type { Evidence, LayerItem, Shape, Word } from "../api";
import { centroid, fmt, polygonArea, roomArea, roomName } from "../lib/takeoff";
import type { Room } from "../lib/takeoff";

type View = { x: number; y: number; k: number };
export type ViewerHandle = { focus: (box: number[] | null) => void };
export type Tool = "select" | "distance" | "area" | "calibrate";
export type Measure = { kind: "distance" | "area"; points: number[][] };

type Props = {
  src: string;
  size: [number, number];
  evidence: Evidence[];
  layer: LayerItem[] | null;
  words: Word[] | null;
  rooms: Room[] | null;
  mPerPx: number | null;
  roomId: string | null;
  onRoom: (id: string | null) => void;
  tool: Tool;
  measures: Measure[];
  onMeasure: (m: Measure) => void;
  onCalibrate: (px: number) => void;
  hoverId: string | null;
  selectedId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string | null) => void;
  children?: ReactNode;
};

const KIND_COLOR: Record<string, string> = {
  door: "#b8432f", window: "#0d7f9b", toilet: "#7a6a00", washbasin: "#7a6a00", bathtub: "#7a6a00",
  shower: "#7a6a00", sink: "#7a6a00", wall: "#7a7a7a", slab: "#9a9a9a", stair: "#2b8a3e",
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
const dist = (a: number[], b: number[]) => Math.hypot(a[0] - b[0], a[1] - b[1]);

const Viewer = forwardRef<ViewerHandle, Props>(function Viewer(p, ref) {
  const wrap = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<View>({ x: 0, y: 0, k: 0.1 });
  const [anim, setAnim] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const [draft, setDraftState] = useState<number[][]>([]);
  const draftRef = useRef<number[][]>([]);
  const setDraft = (d: number[][]) => { draftRef.current = d; setDraftState(d); };
  const [cursor, setCursor] = useState<number[] | null>(null);
  const [W, H] = p.size;
  const m = p.mPerPx;

  const animate = () => { setAnim(true); window.setTimeout(() => setAnim(false), 400); };
  const fitBox = useCallback((b: number[], pad: number, maxK: number) => {
    const el = wrap.current;
    if (!el) return;
    const cw = el.clientWidth, ch = el.clientHeight;
    const k = Math.min((cw * (1 - 2 * pad)) / Math.max(b[2] - b[0], 20), (ch * (1 - 2 * pad)) / Math.max(b[3] - b[1], 20), maxK);
    animate();
    setView({ k, x: cw / 2 - ((b[0] + b[2]) / 2) * k, y: ch / 2 - ((b[1] + b[3]) / 2) * k });
  }, []);
  const fit = useCallback(() => fitBox([0, 0, W, H], 0.06, 100), [W, H, fitBox]);
  // Zoom to a region; a region spanning most of the sheet shows the whole sheet instead of cropping it
  const focus = useCallback((b: number[] | null) => {
    if (b && b[2] - b[0] < W / 2 && b[3] - b[1] < H / 2) fitBox(b, 0.22, 3);
    else fit();
  }, [W, H, fitBox, fit]);
  useImperativeHandle(ref, () => ({ focus }), [focus]);

  useEffect(() => { setLoaded(false); }, [p.src]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setDraft([]); }, [p.tool]);
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

  const { onMeasure } = p;
  const finishArea = useCallback((pts: number[][]) => {
    if (pts.length >= 3) onMeasure({ kind: "area", points: pts });
    draftRef.current = [];
    setDraftState([]);
  }, [onMeasure]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDraft([]);
      if (e.key === "Enter" && p.tool === "area") finishArea(draft);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [p.tool, draft, finishArea]);

  const zoom = (f: number) => {
    const el = wrap.current!;
    animate();
    setView((v) => zoomAt(v, clampK(v.k * f), el.clientWidth / 2, el.clientHeight / 2));
  };
  const toImage = (e: { clientX: number; clientY: number }) => {
    const r = wrap.current!.getBoundingClientRect();
    return [(e.clientX - r.left - view.x) / view.k, (e.clientY - r.top - view.y) / view.k];
  };

  const onDown = (e: PointerEvent) => { drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false }; };
  const onMove = (e: PointerEvent) => {
    if (p.tool !== "select") setCursor(toImage(e));
    const d = drag.current;
    if (!d || !(e.buttons & 1)) return;
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
    if (d.moved) setView((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }));
  };
  const onUp = (e: PointerEvent) => {
    const moved = drag.current?.moved;
    window.setTimeout(() => { drag.current = null; });
    if (moved || p.tool === "select" || (e.target as Element).closest(".viewer-ui, .viewer-tools")) return;
    const pt = toImage(e);
    const draft = draftRef.current;
    if (p.tool === "area") {
      if (draft.length >= 3 && dist(pt, draft[0]) * view.k < 12) finishArea(draft);
      else setDraft([...draft, pt]);
    } else if (draft.length === 0) setDraft([pt]);
    else {
      if (p.tool === "distance") p.onMeasure({ kind: "distance", points: [draft[0], pt] });
      else p.onCalibrate(dist(draft[0], pt));
      setDraft([]);
    }
  };

  const label = (text: string) => (e: MouseEvent) => {
    const r = wrap.current!.getBoundingClientRect();
    setTip({ x: e.clientX - r.left + 14, y: e.clientY - r.top + 14, text });
  };
  const noTip = () => setTip(null);
  const clicked = () => !drag.current?.moved && p.tool === "select";

  const evIds = new Set(p.evidence.map((e) => e.id));
  const placed = p.evidence.filter((e) => e.polygon || e.bbox);
  const fs = 12.5 / view.k; // label size in image px that renders at 12.5 screen px
  const lengthText = (px: number) => (m ? `${fmt(px * m, 2)} m` : `${Math.round(px)} px`);
  const areaText = (px2: number) => (m ? `${fmt(px2 * m * m, 2)} m²` : `${Math.round(px2)} px²`);
  const tag = (at: number[], text: string, cls = "") => (
    <text className={"tag " + cls} x={at[0]} y={at[1]} fontSize={fs} strokeWidth={fs / 3.2}>{text}</text>
  );
  const live = draft.length && cursor ? [...draft, cursor] : draft;
  const mid = (a: number[], b: number[]) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - fs * 0.6];

  return (
    <div className={"viewer tool-" + p.tool} ref={wrap} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}
      onPointerLeave={() => { drag.current = null; noTip(); setCursor(null); }}>
      <div className={"stage" + (anim ? " anim" : "")} style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})`, width: W, height: H }}>
        <img ref={(el) => { if (el?.complete && el.naturalWidth) setLoaded(true); }} src={p.src} width={W} height={H} draggable={false} onLoad={() => setLoaded(true)} alt="Drawing sheet" />
        <svg className="overlay" width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
          {p.rooms?.map((r) => (
            <polygon key={r.id} className={"room" + (p.roomId === r.id ? " on" : "")} points={r.polygon.map((q) => q.join(",")).join(" ")}
              vectorEffect="non-scaling-stroke" onClick={() => { if (clicked()) p.onRoom(p.roomId === r.id ? null : r.id); }}
              onMouseMove={label(`${roomName(r)}${m ? ` · ${fmt(roomArea(r, m))} m²` : ""}`)} onMouseLeave={noTip} />
          ))}
          {p.layer?.filter((l) => !evIds.has(l.id) && l.kind !== "room" && l.kind !== "unit").map((l) => (
            <g key={"l" + l.id} onMouseMove={label(l.label)} onMouseLeave={noTip}>
              <ShapeEl e={l} cls="lay" color={KIND_COLOR[l.kind] || "#888"} />
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
              onClick={() => { if (clicked()) p.onSelect(e.id === p.selectedId ? null : e.id); }}>
              <ShapeEl e={e} cls={"ev" + (e.approximate ? " approx" : "") + (p.hoverId === e.id || p.selectedId === e.id ? " on" : "")} />
            </g>
          ))}
          {m && p.rooms?.filter((r) => r.id === p.roomId || (r.printed_area_m2 == null && Math.min(boxOf(r)![2] - boxOf(r)![0], boxOf(r)![3] - boxOf(r)![1]) * view.k > 72)).map((r) => {
            const c = centroid(r.polygon);
            return r.id === p.roomId ? (
              <g key={"t" + r.id}>
                {tag([c[0], c[1] - fs * 0.25], roomName(r), "name sel")}
                {tag([c[0], c[1] + fs * 1.05], `${fmt(roomArea(r, m))} m²`, "sel")}
              </g>
            ) : <g key={"t" + r.id}>{tag([c[0], c[1] + fs * 2.2], `${fmt(roomArea(r, m))} m²`, "area")}</g>;
          })}
          <g className="measures">
            {p.measures.map((ms, i) => ms.kind === "distance" ? (
              <g key={i}>
                <line x1={ms.points[0][0]} y1={ms.points[0][1]} x2={ms.points[1][0]} y2={ms.points[1][1]} vectorEffect="non-scaling-stroke" />
                {ms.points.map((q, n) => <circle key={n} cx={q[0]} cy={q[1]} r={3.5 / view.k} />)}
                {tag(mid(ms.points[0], ms.points[1]), lengthText(dist(ms.points[0], ms.points[1])), "m")}
              </g>
            ) : (
              <g key={i}>
                <polygon points={ms.points.map((q) => q.join(",")).join(" ")} vectorEffect="non-scaling-stroke" />
                {tag(centroid(ms.points), areaText(polygonArea(ms.points)), "m")}
              </g>
            ))}
            {live.length > 0 && (
              <g className="draft">
                <polyline points={live.map((q) => q.join(",")).join(" ")} vectorEffect="non-scaling-stroke" />
                {draft.map((q, n) => <circle key={n} cx={q[0]} cy={q[1]} r={3.5 / view.k} />)}
                {live.length >= 2 && tag(mid(live[live.length - 2], live[live.length - 1]),
                  p.tool === "area" && live.length >= 3 ? areaText(polygonArea(live)) : lengthText(dist(live[live.length - 2], live[live.length - 1])), "m")}
              </g>
            )}
          </g>
        </svg>
      </div>
      {!loaded && <div className="viewer-loading">Loading drawing…</div>}
      {tip && p.tool === "select" && <div className="tip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
      <div className="viewer-ui">{p.children}</div>
      <div className="viewer-tools">
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
