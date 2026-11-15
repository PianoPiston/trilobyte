import { AbsoluteFill, Audio, Easing, Img, Sequence, continueRender, delayRender, getInputProps, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import timing from "./timing.json";

// Stoa brand (stoabuild.com), same tokens as the Trilobyte web app
const BG = "#f2f3f5", INK = "#001d00", INK2 = "#2c412b", INK3 = "#617061", MOSS = "#adb7ad", MARK = "#c2452d";
const SERIF = "Playfair, Georgia, serif", SANS = "Inter, system-ui, sans-serif", MONO = "JetBrainsMono, monospace";
const FPS = 30, FADE = 10, W = 1920, H = 1080;

const fontsReady = delayRender("fonts");
Promise.all([["Playfair", "playfair-display"], ["Inter", "inter"], ["JetBrainsMono", "jetbrains-mono"]].map(([family, file]) =>
  new FontFace(family, `url(${staticFile(`fonts/${file}-latin-wght-normal.woff2`)})`, { weight: "100 900" }).load().then((f) => document.fonts.add(f))))
  .then(() => continueRender(fontsReady));

// A clip is a still or a numbered frame sequence (public/cap/<seq>-000.png ...), shown until a fraction of its scene.
// cam: the camera moves from the first to the second [centre x, centre y, zoom], in image fractions.
type Cam = [number, number, number];
type Clip = { img?: string; seq?: string; n?: number; until: number; cam: [Cam, Cam] };
type Visual =
  | { kind: "title" } | { kind: "problem" } | { kind: "trust" } | { kind: "close" }
  | { kind: "shots"; label: string; clips: Clip[] };

const VISUALS: Record<string, Visual> = {
  title: { kind: "title" },
  problem: { kind: "problem" },
  drop: { kind: "shots", label: "Drop in any floor plan", clips: [
    { img: "home", until: 0.3, cam: [[0.72, 0.3, 1.15], [0.72, 0.3, 1.22]] },
    { img: "uploading", until: 0.55, cam: [[0.72, 0.3, 1.3], [0.72, 0.3, 1.4]] },
    { img: "up-summary", until: 1, cam: [[0.5, 0.5, 1], [0.42, 0.5, 1.1]] }] },
  measured: { kind: "shots", label: "Rooms found and measured", clips: [
    { img: "up-summary", until: 1, cam: [[0.35, 0.55, 1.2], [0.84, 0.3, 1.6]] }] },
  concrete: { kind: "shots", label: "How much concrete for this floor?", clips: [
    { img: "up-summary", until: 0.3, cam: [[0.84, 0.72, 1.6], [0.84, 0.7, 1.7]] },
    { img: "up-concrete", until: 1, cam: [[0.55, 0.45, 1.05], [0.6, 0.4, 1.2]] }] },
  prices: { kind: "shots", label: "Live prices from Finnish suppliers via context.dev", clips: [
    { img: "sw-materials", until: 0.55, cam: [[0.85, 0.45, 1.3], [0.85, 0.45, 1.4]] },
    { img: "sw-materials-2", until: 1, cam: [[0.85, 0.5, 1.4], [0.85, 0.6, 1.5]] }] },
  room: { kind: "shots", label: "Price one room", clips: [{ img: "sw-room-price", until: 1, cam: [[0.5, 0.5, 1], [0.6, 0.45, 1.12]] }] },
  ask: { kind: "shots", label: "Ask in plain language", clips: [
    { seq: "sw-type", n: 34, until: 0.42, cam: [[0.83, 0.11, 1.9], [0.83, 0.11, 1.9]] },
    { img: "sw-kitchen", until: 1, cam: [[0.5, 0.5, 1], [0.55, 0.5, 1.12]] }] },
  measure: { kind: "shots", label: "Measure distances and areas", clips: [
    { img: "measure-distance", until: 0.45, cam: [[0.35, 0.5, 1.4], [0.35, 0.5, 1.45]] },
    { img: "measure-area", until: 1, cam: [[0.35, 0.55, 1.45], [0.35, 0.55, 1.5]] }] },
  model3d: { kind: "shots", label: "Every plan in 3D", clips: [
    { seq: "up3d", n: 60, until: 0.5, cam: [[0.38, 0.55, 1.25], [0.38, 0.55, 1.3]] },
    { seq: "sw3d", n: 60, until: 1, cam: [[0.36, 0.55, 1.25], [0.36, 0.55, 1.3]] }] },
  trust: { kind: "trust" },
  close: { kind: "close" },
};

type T = { id: string; say: string; text: string; vo: string; voSec: number; sec: number };
const SCENES = (timing.scenes as T[]).map((t) => ({ ...t, v: VISUALS[t.id] }));
export const TOTAL = Math.ceil(timing.total * FPS);

const ease = (f: number, a: number, b: number) => interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const Caption = ({ text, dur }: { text: string; dur: number }) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 8, dur - 8, dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: 200, right: 200, bottom: 44, opacity: o, textAlign: "center" }}>
      <span style={{ background: "rgba(0,29,0,0.86)", color: "white", fontSize: 32, lineHeight: 1.5, padding: "8px 20px", borderRadius: 8,
        fontFamily: SANS, boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone" }}>{text}</span>
    </div>
  );
};

const ClipView = ({ c, from, to }: { c: Clip; from: number; to: number }) => {
  const f = useCurrentFrame();
  const k = Easing.inOut(Easing.quad)(ease(f, from, to));
  const [x, y, z] = [0, 1, 2].map((i) => c.cam[0][i] + (c.cam[1][i] - c.cam[0][i]) * k);
  // translate so (x, y) sits at the frame centre, without uncovering the frame edges
  const tx = Math.min(0, Math.max(W * (1 - z), W / 2 - x * W * z)), ty = Math.min(0, Math.max(H * (1 - z), H / 2 - y * H * z));
  const src = c.seq ? `cap/${c.seq}-${String(Math.min(c.n! - 1, Math.floor(ease(f, from, to) * c.n!))).padStart(3, "0")}.png` : `cap/${c.img}.png`;
  return (
    <AbsoluteFill style={{ opacity: ease(f, from - FADE, from), transform: `translate(${tx}px, ${ty}px) scale(${z})`, transformOrigin: "0 0" }}>
      <Img src={staticFile(src)} style={{ width: "100%", height: "100%" }} />
    </AbsoluteFill>
  );
};

const Shots = ({ s, dur }: { s: Extract<Visual, { kind: "shots" }>; dur: number }) => {
  const f = useCurrentFrame();
  let start = 0;
  return (
    <AbsoluteFill style={{ background: BG }}>
      {s.clips.map((c, i) => {
        const from = start; start = Math.round(c.until * dur);
        return f >= from - FADE && f < start + FADE ? <ClipView key={i} c={c} from={from} to={start} /> : null;
      })}
      <div style={{ position: "absolute", top: 28, left: 28, background: INK, color: "white", fontSize: 30, fontWeight: 500, fontFamily: SANS,
        padding: "12px 24px", borderRadius: 10, boxShadow: "0 10px 30px -12px rgba(0,0,0,.45)", opacity: ease(f, 4, 16), letterSpacing: "-0.01em" }}>{s.label}</div>
    </AbsoluteFill>
  );
};

const Title = () => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const p = spring({ frame: f, fps, config: { damping: 20 } });
  return (
    <AbsoluteFill style={{ background: BG }}>
      <div style={{ position: "absolute", left: 160, top: 300, width: 900 }}>
        <div style={{ fontFamily: SERIF, fontSize: 170, color: INK, letterSpacing: "-0.03em", opacity: p, transform: `translateY(${(1 - p) * 30}px)` }}>Trilobyte</div>
        <div style={{ fontFamily: SERIF, fontSize: 56, color: INK2, marginTop: 18, lineHeight: 1.15, opacity: ease(f, 14, 30) }}>Measure and price<br />any floor plan.</div>
        <div style={{ fontFamily: SANS, fontSize: 26, color: INK3, marginTop: 64, opacity: ease(f, 24, 40) }}>Junction 2026 · Stoa: Make Blueprints Talk · Verda</div>
      </div>
      <div style={{ position: "absolute", right: 150, top: 150, width: 620, height: 780, background: "white", borderRadius: 14, overflow: "hidden",
        boxShadow: "0 0 0 1px #0000000f, 0 30px 60px -30px #0000004d", opacity: ease(f, 8, 28), transform: `translateY(${(1 - ease(f, 8, 28)) * 24}px)` }}>
        <Img src={staticFile("cap/plan.png")} style={{ width: "100%", height: "100%", objectFit: "contain" }} />
      </div>
    </AbsoluteFill>
  );
};

const Problem = () => {
  const f = useCurrentFrame();
  const items = ["Hours with a scale ruler", "A spreadsheet for every material", "Calls to suppliers for prices"];
  return (
    <AbsoluteFill style={{ background: BG, padding: "210px 180px" }}>
      <div style={{ fontFamily: SANS, fontSize: 30, color: INK3, opacity: ease(f, 0, 12) }}>A site manager asks:</div>
      <div style={{ fontFamily: SERIF, fontSize: 96, color: INK, lineHeight: 1.08, letterSpacing: "-0.02em", marginTop: 20, maxWidth: 1400, opacity: ease(f, 6, 22) }}>
        “How much concrete do I order for this floor?”</div>
      <div style={{ display: "flex", gap: 40, marginTop: 110 }}>
        {items.map((t, i) => {
          const o = ease(f, (4.6 + i * 1.1) * FPS, (4.6 + i * 1.1) * FPS + 12);
          return <div key={i} style={{ flex: 1, opacity: o, transform: `translateY(${(1 - o) * 16}px)`, borderTop: `2px solid ${MARK}`, paddingTop: 22,
            fontFamily: SANS, fontSize: 36, color: INK2 }}>{t}</div>;
        })}
      </div>
    </AbsoluteFill>
  );
};

const Trust = () => {
  const f = useCurrentFrame();
  const stats: [string, string][] = [
    ["Exact", "rooms and areas from CAD and BIM geometry"],
    ["99.85%", "area answers correct on held-out test drawings (650 of 651)"],
    ["Flagged", "on scans the scale is estimated, shown and marked for a check"],
    ["< €0.02", "per 1,000 questions with Qwen3.5-4B fine-tuned on Verda GPUs"]];
  const at = [0.3, 2.8, 8.2, 11.6];
  return (
    <AbsoluteFill style={{ background: INK, padding: "150px 170px" }}>
      <div style={{ fontFamily: SERIF, fontSize: 76, color: "white", letterSpacing: "-0.02em", opacity: ease(f, 0, 14) }}>Numbers you can order from</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "70px 110px", marginTop: 90 }}>
        {stats.map(([big, small], i) => {
          const o = ease(f, at[i] * FPS, at[i] * FPS + 14);
          return <div key={i} style={{ opacity: o, transform: `translateY(${(1 - o) * 16}px)` }}>
            <div style={{ fontFamily: MONO, fontSize: 92, fontWeight: 500, color: "white", letterSpacing: "-0.03em" }}>{big}</div>
            <div style={{ fontFamily: SANS, fontSize: 32, color: MOSS, marginTop: 8, lineHeight: 1.35 }}>{small}</div>
          </div>;
        })}
      </div>
    </AbsoluteFill>
  );
};

const Close = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: BG, justifyContent: "center", alignItems: "center", textAlign: "center" }}>
      <div style={{ fontFamily: SERIF, fontSize: 150, color: INK, letterSpacing: "-0.03em", opacity: ease(f, 0, 16) }}>Trilobyte</div>
      <div style={{ fontFamily: SERIF, fontSize: 54, color: INK2, marginTop: 12, opacity: ease(f, 14, 30) }}>From drawing to order list in a minute.</div>
      <div style={{ fontFamily: SANS, fontSize: 28, color: INK3, marginTop: 56, opacity: ease(f, 30, 46) }}>Web app · API · MCP server · every answer marked on the sheet</div>
    </AbsoluteFill>
  );
};

export const Trilobyte = () => {
  const captions = !getInputProps().noCaptions;
  let from = 0;
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Audio src={staticFile("music.wav")} volume={0.06} />
      {SCENES.map((sc, i) => {
        const dur = Math.round(sc.sec * FPS); const start = from; from += dur; const v = sc.v;
        return (
          <Sequence key={i} from={start} durationInFrames={dur + (i < SCENES.length - 1 ? 8 : 0)}>
            <SceneFade>
              {v.kind === "title" && <Title />}
              {v.kind === "problem" && <Problem />}
              {v.kind === "shots" && <Shots s={v} dur={dur} />}
              {v.kind === "trust" && <Trust />}
              {v.kind === "close" && <Close />}
            </SceneFade>
            <Sequence from={i === 0 ? 18 : 6}><Audio src={staticFile(sc.vo)} /></Sequence>
            {captions && <Caption text={sc.text} dur={dur} />}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

// each scene fades in over the tail of the previous one
const SceneFade = ({ children }: { children: React.ReactNode }) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ opacity: ease(f, 0, 8) }}>{children}</AbsoluteFill>;
};
