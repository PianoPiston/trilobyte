import { AbsoluteFill, Audio, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

const NAVY = "#14284a", ACCENT = "#e8743b", PAPER = "#f5f1e8";
const FPS = 30;

import timing from "./timing.json";

type Visual =
  | { kind: "title"; title: string; sub: string }
  | { kind: "bullets"; title: string; bullets: string[] }
  | { kind: "shot"; img: string; label: string; focus: [number, number, number] }
  | { kind: "stats"; title: string; stats: [string, string][] }
  | { kind: "pipeline" }
  | { kind: "split"; title: string; bullets: string[]; img: string; focus: [number, number, number] };

// visuals per narration scene (the spoken text and durations come from script.json -> src/timing.json)
const VISUALS: Record<string, Visual> = {
  title: { kind: "title", title: "Trilobyte", sub: "Make blueprints talk: answers you can verify in seconds" },
  problem: { kind: "bullets", title: "The problem", bullets: [
    "Site engineers spend hours hunting quantities in drawings",
    "Scans, PDFs, CAD and BIM, all in different formats",
    "AI that guesses is useless on site: a wrong number costs money"] },
  upload: { kind: "shot", img: "01-home", label: "Upload any drawing · ask in English or Finnish", focus: [0.5, 0.35, 1.12] },
  cad: { kind: "shot", img: "02-swiss-bedrooms", label: "CAD → exact answer: 8 bedrooms, each highlighted", focus: [0.45, 0.5, 1.18] },
  ifc: { kind: "shot", img: "07-ifc", label: "BIM models → answers cite IFC element IDs", focus: [0.75, 0.4, 1.15] },
  scan: { kind: "shot", img: "05-cubicasa-windows", label: "Scans: symbol detector + printed-text reading", focus: [0.45, 0.5, 1.15] },
  decide: { kind: "pipeline" },
  ranked: { kind: "shot", img: "04-cubicasa-bedrooms", label: "Best answer first, alternatives below", focus: [0.86, 0.6, 1.4] },
  context: { kind: "split", title: "Context, not just pixels", bullets: [
    "context.dev web search API pulls in project information",
    "Archive records for historic drawings: 58% → 94%",
    "In a company: internal documentation in the same slot",
    "No need for perfect detection every time"], img: "08-historic", focus: [0.82, 0.3, 1.0] },
  results: { kind: "stats", title: "Measured on held-out drawings", stats: [
    ["47% → 81%", "accuracy: zero-shot → fine-tuned hybrid"],
    ["99.2%", "precision when it answers on its own"],
    ["€0.016", "per 1,000 questions"],
    ["100% / 99.8%", "BIM models / CAD drawings"]] },
  close: { kind: "bullets", title: "Trilobyte", bullets: [
    "Standardized drawing format · web app · API · MCP server",
    "Small fine-tuned models + exact geometry: cheap, private, verifiable",
    "Every answer points to its evidence"] },
};
type T = { id: string; say: string; vo: string; voSec: number; sec: number };
const SCENES = (timing.scenes as T[]).map((t) => ({ ...t, v: VISUALS[t.id] }));
export const TOTAL = Math.ceil(timing.total * FPS);

const Caption = ({ text, dur }: { text: string; dur: number }) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 10, dur - 10, dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: 160, right: 160, bottom: 48, opacity: o, textAlign: "center" }}>
      <span style={{ background: "rgba(10,20,40,0.82)", color: "white", fontSize: 34, lineHeight: 1.45, padding: "10px 22px",
        borderRadius: 10, fontFamily: "Inter, Helvetica, Arial, sans-serif", boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone" }}>{text}</span>
    </div>
  );
};

const Brand = () => (
  <div style={{ position: "absolute", top: 34, left: 48, color: NAVY, fontSize: 30, fontWeight: 800, fontFamily: "Inter, Helvetica, Arial, sans-serif", letterSpacing: 1 }}>
    ▦ TRILOBYTE
  </div>
);

const Title = ({ s }: { s: Extract<Visual, { kind: "title" }> }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 18 } });
  return (
    <AbsoluteFill style={{ background: `linear-gradient(135deg, ${NAVY}, #2a4a7f)`, justifyContent: "center", alignItems: "center", fontFamily: "Inter, Helvetica, Arial, sans-serif" }}>
      <div style={{ fontSize: 150, color: "white", fontWeight: 900, letterSpacing: 4, transform: `scale(${0.85 + 0.15 * p})`, opacity: p }}>▦ {s.title}</div>
      <div style={{ fontSize: 46, color: "#ffd9c4", marginTop: 24, opacity: interpolate(f, [15, 35], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }) }}>{s.sub}</div>
      <div style={{ position: "absolute", bottom: 150, color: "#9fb3d6", fontSize: 28 }}>Junction 2026 · Stoa challenge · Verda compute</div>
    </AbsoluteFill>
  );
};

const Bullets = ({ s }: { s: Extract<Visual, { kind: "bullets" }> }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER, padding: "150px 180px", fontFamily: "Inter, Helvetica, Arial, sans-serif" }}>
      <Brand />
      <div style={{ fontSize: 84, fontWeight: 800, color: NAVY, marginBottom: 50 }}>{s.title}</div>
      {s.bullets.map((b, i) => {
        const o = interpolate(f, [20 + i * 25, 40 + i * 25], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return <div key={i} style={{ fontSize: 50, color: "#1e2a3a", margin: "26px 0", opacity: o, transform: `translateX(${(1 - o) * 40}px)` }}>
          <span style={{ color: ACCENT, fontWeight: 900, marginRight: 24 }}>—</span>{b}</div>;
      })}
    </AbsoluteFill>
  );
};

const Shot = ({ s, dur }: { s: Extract<Visual, { kind: "shot" }>; dur: number }) => {
  const f = useCurrentFrame();
  const [fx, fy, z] = s.focus;
  const k = interpolate(f, [0, dur], [0, 1], { extrapolateRight: "clamp" });
  const scale = 1 + (z - 1) * k;
  return (
    <AbsoluteFill style={{ background: "#0d1a30" }}>
      <AbsoluteFill style={{ transform: `scale(${scale})`, transformOrigin: `${fx * 100}% ${fy * 100}%` }}>
        <Img src={staticFile(`shots/${s.img}.png`)} style={{ width: "100%", height: "100%" }} />
      </AbsoluteFill>
      <div style={{ position: "absolute", top: 90, left: 48, background: ACCENT, color: "white", fontSize: 36, fontWeight: 700,
        padding: "12px 26px", borderRadius: 10, fontFamily: "Inter, Helvetica, Arial, sans-serif", boxShadow: "0 6px 24px rgba(0,0,0,.25)",
        opacity: interpolate(f, [5, 20], [0, 1], { extrapolateRight: "clamp", extrapolateLeft: "clamp" }) }}>{s.label}</div>
    </AbsoluteFill>
  );
};

const Stats = ({ s }: { s: Extract<Visual, { kind: "stats" }> }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: NAVY, padding: "140px 160px", fontFamily: "Inter, Helvetica, Arial, sans-serif" }}>
      <div style={{ fontSize: 70, fontWeight: 800, color: "white", marginBottom: 60 }}>{s.title}</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "50px 80px" }}>
        {s.stats.map(([big, small], i) => {
          const o = interpolate(f, [15 + i * 30, 35 + i * 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return <div key={i} style={{ opacity: o }}>
            <div style={{ fontSize: 96, fontWeight: 900, color: "#ffb38a" }}>{big}</div>
            <div style={{ fontSize: 36, color: "#c9d6ee" }}>{small}</div>
          </div>;
        })}
      </div>
    </AbsoluteFill>
  );
};

const box = (o: number, extra: object = {}) => ({ opacity: o, transform: `translateY(${(1 - o) * 20}px)`, background: "white", borderRadius: 14,
  padding: "18px 26px", fontSize: 32, fontWeight: 700, color: NAVY, boxShadow: "0 6px 22px rgba(0,0,0,.18)", ...extra });

const Pipeline = ({ dur }: { dur: number }) => {
  const f = useCurrentFrame();
  const at = (sec: number) => interpolate(f, [sec * FPS, sec * FPS + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const sources: [string, string, number][] = [
    ["CAD parser (DXF)", "exact geometry", 5.2], ["BIM parser (IFC)", "exact quantities", 6.3], ["Symbol detector", "doors · windows · fixtures", 7.5],
    ["Printed-text reader", "OCR / PDF text", 8.6], ["Fine-tuned vision model", "Qwen 4B + LoRA", 9.8]];
  return (
    <AbsoluteFill style={{ background: `linear-gradient(135deg, ${NAVY}, #24467a)`, fontFamily: "Inter, Helvetica, Arial, sans-serif", padding: "70px 90px" }}>
      <div style={{ fontSize: 60, fontWeight: 800, color: "white", opacity: at(0.2) }}>Many decision makers, one final judge</div>
      <div style={{ position: "absolute", left: 90, top: 210, display: "flex", flexDirection: "column", gap: 22, width: 560 }}>
        {sources.map(([a, b, t], i) => <div key={i} style={box(at(t))}>{a}<div style={{ fontSize: 22, fontWeight: 500, color: "#5a6b85" }}>{b}</div></div>)}
      </div>
      <div style={{ position: "absolute", left: 690, top: 520, fontSize: 90, color: "#ffb38a", opacity: at(12) }}>→</div>
      <div style={{ position: "absolute", left: 820, top: 420, width: 470, ...box(at(12.2), { background: ACCENT, color: "white", fontSize: 40, textAlign: "center", padding: "40px 30px" }) }}>
        Decision layer<div style={{ fontSize: 26, fontWeight: 500, marginTop: 10 }}>calibrated rules + LLM judge<br />ranks every candidate</div></div>
      <div style={{ position: "absolute", left: 1320, top: 520, fontSize: 90, color: "#ffb38a", opacity: at(14.5) }}>→</div>
      <div style={{ position: "absolute", left: 1450, top: 380, width: 390, ...box(at(14.7), { fontSize: 34 }) }}>
        1. Best answer<div style={{ fontSize: 24, fontWeight: 500, color: "#5a6b85", margin: "6px 0 14px" }}>+ evidence on the drawing + confidence</div>
        2. Alternatives<div style={{ fontSize: 24, fontWeight: 500, color: "#5a6b85", margin: "6px 0 14px" }}>shown below, less confident</div>
        ⚠ Needs check<div style={{ fontSize: 24, fontWeight: 500, color: "#5a6b85", marginTop: 6 }}>when sources disagree</div></div>
    </AbsoluteFill>
  );
};

const Split = ({ s, dur }: { s: Extract<Visual, { kind: "split" }>; dur: number }) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER, fontFamily: "Inter, Helvetica, Arial, sans-serif" }}>
      <Brand />
      <div style={{ position: "absolute", left: 90, top: 140, width: 860 }}>
        <div style={{ fontSize: 66, fontWeight: 800, color: NAVY, marginBottom: 40 }}>{s.title}</div>
        {s.bullets.map((b, i) => {
          const o = interpolate(f, [(1 + i * 3.6) * FPS, (1 + i * 3.6) * FPS + 15], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return <div key={i} style={{ fontSize: 40, color: "#1e2a3a", margin: "24px 0", opacity: o }}><span style={{ color: ACCENT, fontWeight: 900, marginRight: 18 }}>—</span>{b}</div>;
        })}
      </div>
      <div style={{ position: "absolute", right: 70, top: 120, width: 820, height: 760, overflow: "hidden", borderRadius: 16, boxShadow: "0 10px 40px rgba(0,0,0,.25)" }}>
        <Img src={staticFile(`shots/${s.img}.png`)} style={{ width: 1600, position: "absolute", left: interpolate(f, [0, dur], [-780, -760]), top: -30 }} />
      </div>
    </AbsoluteFill>
  );
};

export const Trilobyte = () => {
  let from = 0;
  return (
    <AbsoluteFill>
      <Audio src={staticFile("music.wav")} volume={0.07} />
      {SCENES.map((sc, i) => {
        const dur = Math.round(sc.sec * FPS); const start = from; from += dur; const v = sc.v;
        return (
          <Sequence key={i} from={start} durationInFrames={dur}>
            {v.kind === "title" && <Title s={v} />}
            {v.kind === "bullets" && <Bullets s={v} />}
            {v.kind === "shot" && <Shot s={v} dur={dur} />}
            {v.kind === "stats" && <Stats s={v} />}
            {v.kind === "pipeline" && <Pipeline dur={dur} />}
            {v.kind === "split" && <Split s={v} dur={dur} />}
            <Sequence from={i === 0 ? 18 : 6}><Audio src={staticFile(sc.vo)} /></Sequence>
            <Caption text={sc.say.replace("context dot dev", "context.dev")} dur={dur} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
