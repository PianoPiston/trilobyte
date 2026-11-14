import { AbsoluteFill, Audio, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

const NAVY = "#14284a", ACCENT = "#e8743b", PAPER = "#f5f1e8";
const FPS = 30;

// ---- the script: one scene per narration paragraph (seconds). Edit text/timing here. ----
type Scene =
  | { kind: "title"; sec: number; title: string; sub: string; say: string }
  | { kind: "bullets"; sec: number; title: string; bullets: string[]; say: string }
  | { kind: "shot"; sec: number; img: string; label: string; focus: [number, number, number]; say: string }
  | { kind: "stats"; sec: number; title: string; stats: [string, string][]; say: string };

export const SCENES: Scene[] = [
  { kind: "title", sec: 7, title: "Trilobyte", sub: "Make blueprints talk — answers you can verify in seconds",
    say: "Trilobyte answers questions about construction drawings, and shows you exactly where every answer comes from." },
  { kind: "bullets", sec: 13, title: "The problem", bullets: [
      "Site engineers spend hours hunting quantities in drawings",
      "Doors, windows, room areas, fixtures — across scans, PDFs, CAD and BIM",
      "AI that guesses is useless on site: a wrong number costs money" ],
    say: "Site engineers and foremen spend hours digging quantities out of drawings. A chatbot that guesses doesn't help. On a construction site, a wrong number costs real money." },
  { kind: "shot", sec: 11, img: "01-home", label: "Upload any drawing · ask in Finnish or English", focus: [0.5, 0.35, 1.15],
    say: "So you upload a drawing, a scan, a PDF or a plan, and simply ask, in English or Finnish." },
  { kind: "shot", sec: 14, img: "02-swiss-apartments", label: "CAD drawing → exact answer, every room highlighted", focus: [0.62, 0.45, 1.25],
    say: "When CAD data exists, Trilobyte converts the drawing into a standardized file and answers exactly. Four apartments, every one highlighted on the plan, in milliseconds." },
  { kind: "shot", sec: 11, img: "07-ifc", label: "BIM models → answers cite IFC element IDs", focus: [0.75, 0.4, 1.2],
    say: "For BIM models, answers cite the IFC elements they were computed from." },
  { kind: "shot", sec: 9, img: "05-cubicasa-windows", label: "Scans: symbol detector + printed-text reading", focus: [0.45, 0.5, 1.15],
    say: "Scans are harder. Our symbol detector finds doors, windows and fixtures, and we read every word printed on the sheet." },
  { kind: "shot", sec: 11, img: "04-cubicasa-bedrooms", label: "Ranked candidates · honest \"needs check\"", focus: [0.85, 0.55, 1.35],
    say: "Every source proposes an answer. Trilobyte ranks them, shows the alternatives, and says 'needs check' instead of making something up." },
  { kind: "shot", sec: 10, img: "08-historic", label: "Historic drawings get their context back", focus: [0.75, 0.5, 1.2],
    say: "Historic drawings get their context back from the archives. Accuracy on our historic questions went from 58 to 94 percent." },
  { kind: "stats", sec: 18, title: "Measured on held-out drawings", stats: [
      ["47% → 81%", "accuracy: zero-shot → fine-tuned hybrid"],
      ["99.2%", "precision when it answers on its own"],
      ["€0.016", "per 1,000 questions"],
      ["100% / 99.8%", "BIM models / CAD drawings"] ],
    say: "We fine-tuned a small open model on Verda GPUs and measured everything on drawings the system never saw. When Trilobyte answers on its own, it's right ninety-nine percent of the time, for under two cents per thousand questions." },
  { kind: "bullets", sec: 14, title: "Trilobyte", bullets: [
      "Standardized drawing format · web app · API · MCP server for any agent",
      "Small fine-tuned model + deterministic geometry: cheap, private, future-proof",
      "Every answer points to its evidence" ],
    say: "Standardized data, a web app, an API and an MCP server any agent can use. Small models plus exact geometry: cheap, private, and verifiable. Trilobyte. Every answer points to its evidence." },
];
export const TOTAL = SCENES.reduce((s, x) => s + x.sec * FPS, 0);

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

const Title = ({ s }: { s: Extract<Scene, { kind: "title" }> }) => {
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

const Bullets = ({ s }: { s: Extract<Scene, { kind: "bullets" }> }) => {
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

const Shot = ({ s, dur }: { s: Extract<Scene, { kind: "shot" }>; dur: number }) => {
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

const Stats = ({ s }: { s: Extract<Scene, { kind: "stats" }> }) => {
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

// Voice-over: put your recording at public/voiceover.mp3 (or .wav) and set HAS_VOICEOVER = true, then re-render.
const HAS_VOICEOVER = false;

export const Trilobyte = () => {
  let from = 0;
  return (
    <AbsoluteFill>
      {HAS_VOICEOVER && <Audio src={staticFile("voiceover.mp3")} />}
      {SCENES.map((s, i) => {
        const dur = s.sec * FPS; const start = from; from += dur;
        return (
          <Sequence key={i} from={start} durationInFrames={dur}>
            {s.kind === "title" && <Title s={s} />}
            {s.kind === "bullets" && <Bullets s={s} />}
            {s.kind === "shot" && <Shot s={s} dur={dur} />}
            {s.kind === "stats" && <Stats s={s} />}
            <Caption text={s.say} dur={dur} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
