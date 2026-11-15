import type { CSSProperties, ReactNode } from "react";
import "@fontsource-variable/inter";
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import timing from "./timing.json";

const INK = "#11201e";
const INK_2 = "#19312b";
const PAPER = "#f4f5f0";
const SURFACE = "#fdfdf9";
const MINT = "#29b887";
const MINT_LIGHT = "#7ce0b9";
const MINT_SOFT = "#e1f4eb";
const CORAL = "#e36553";
const CORAL_SOFT = "#fbeae5";
const AMBER = "#d59b3c";
const MUTED = "#68756f";
const FPS = 30;

type SceneTiming = { id: string; say: string; vo: string; sec: number };
const scenes = timing.scenes as SceneTiming[];
export const TOTAL = Math.ceil(timing.total * FPS);

const reveal = (frame: number, start: number, length = 16) =>
  interpolate(frame, [start, start + length], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const entrance = (frame: number, start: number, length = 16): CSSProperties => {
  const opacity = reveal(frame, start, length);
  return { opacity, transform: `translateY(${(1 - opacity) * 24}px)` };
};

const cleanNarration = (text: string) =>
  text
    .replaceAll("Drift C I", "DriftCI")
    .replaceAll("C I", "CI")
    .replaceAll("Context dot dev", "Context.dev")
    .replaceAll("S D K", "SDK")
    .replaceAll("O S V", "OSV");

const Logo = ({ light = false, size = 34 }: { light?: boolean; size?: number }) => (
  <div style={{ display: "flex", alignItems: "center", gap: size * 0.34, fontFamily: "Inter Variable, Inter, sans-serif" }}>
    <div
      style={{
        width: size * 1.12,
        height: size * 1.12,
        borderRadius: size * 0.28,
        display: "grid",
        placeItems: "center",
        background: MINT,
        transform: "rotate(-4deg)",
        boxShadow: "0 8px 28px rgba(41,184,135,.16)",
      }}
    >
      <svg width={size * 0.7} height={size * 0.7} viewBox="0 0 28 28" fill="none">
        <path d="M2 15h5l3-9 5 17 4-12 3 4h4" stroke="#0c3024" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
    <div style={{ color: light ? "#f3f8f4" : INK, fontSize: size, lineHeight: 1, fontWeight: 740, letterSpacing: -size * 0.04 }}>
      Drift<span style={{ color: light ? MINT_LIGHT : "#127353" }}>CI</span>
    </div>
  </div>
);

const Kicker = ({ children, light = false }: { children: ReactNode; light?: boolean }) => (
  <div style={{ color: light ? MINT_LIGHT : "#127353", fontSize: 18, fontWeight: 720, letterSpacing: 2.7, textTransform: "uppercase" }}>
    {children}
  </div>
);

const Caption = ({ text, duration }: { text: string; duration: number }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 8, duration - 8, duration], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div style={{ position: "absolute", zIndex: 40, left: 140, right: 140, bottom: 30, textAlign: "center", opacity }}>
      <span
        style={{
          display: "inline",
          background: "rgba(8,22,19,.92)",
          color: "#f6faf7",
          borderRadius: 9,
          padding: "10px 20px",
          fontSize: 27,
          lineHeight: 1.48,
          fontWeight: 480,
          letterSpacing: -0.25,
          boxDecorationBreak: "clone",
          WebkitBoxDecorationBreak: "clone",
          boxShadow: "0 5px 24px rgba(0,0,0,.16)",
        }}
      >
        {cleanNarration(text)}
      </span>
    </div>
  );
};

const SceneHeading = ({ kicker, title, light = false, right }: { kicker: string; title: string; light?: boolean; right?: ReactNode }) => (
  <div style={{ position: "absolute", top: 58, left: 76, right: 76, display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 40 }}>
    <div>
      <Kicker light={light}>{kicker}</Kicker>
      <div style={{ marginTop: 13, color: light ? "#f4faf6" : INK, fontSize: 55, lineHeight: 1.12, fontWeight: 710, letterSpacing: -2.2 }}>{title}</div>
    </div>
    {right}
  </div>
);

const AppFrame = ({ shot, pan = 0 }: { shot: string; pan?: number }) => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [24, 360], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", background: SURFACE, overflow: "hidden" }}>
      <div style={{ height: 38, flex: "0 0 auto", display: "flex", alignItems: "center", gap: 7, padding: "0 16px", background: "#e9ede6", borderBottom: "1px solid #d8ded4" }}>
        {[CORAL, AMBER, MINT].map((color) => <span key={color} style={{ width: 9, height: 9, borderRadius: 9, background: color, opacity: 0.75 }} />)}
        <div style={{ marginLeft: 16, color: "#64736c", fontSize: 12, fontFamily: "monospace" }}>driftci.ajc.contexio.fi</div>
        <div style={{ marginLeft: "auto", color: "#7d8a83", fontSize: 10, fontWeight: 700, letterSpacing: 1.1 }}>VERIFIED PRODUCT CAPTURE</div>
      </div>
      <div style={{ position: "relative", flex: 1, overflow: "hidden", background: PAPER }}>
        <Img src={staticFile(`shots/${shot}.png`)} style={{ display: "block", width: "100%", transform: `translateY(${-progress * pan}px)` }} />
      </div>
    </div>
  );
};

const ShotScene = ({ shot, kicker, title, chips, pan }: { shot: string; kicker: string; title: string; chips: string[]; pan: number }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: PAPER, fontFamily: "Inter Variable, Inter, sans-serif" }}>
      <SceneHeading
        kicker={kicker}
        title={title}
        right={
          <div style={{ display: "flex", gap: 10, paddingBottom: 4 }}>
            {chips.map((chip, index) => (
              <div key={chip} style={{ ...entrance(frame, 12 + index * 8), padding: "10px 15px", borderRadius: 9, background: MINT_SOFT, color: "#176448", fontSize: 15, fontWeight: 680, whiteSpace: "nowrap" }}>{chip}</div>
            ))}
          </div>
        }
      />
      <div style={{ position: "absolute", left: 70, right: 70, top: 205, height: 690, borderRadius: 18, overflow: "hidden", border: "1px solid #d4dbd0", boxShadow: "0 22px 60px rgba(25,43,36,.14)", ...entrance(frame, 4, 20) }}>
        <AppFrame shot={shot} pan={pan} />
      </div>
    </AbsoluteFill>
  );
};

const Hook = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const title = spring({ frame, fps, config: { damping: 18, stiffness: 90 } });
  const alerts = [
    ["MODEL LIFECYCLE", "Retirement information changed", 105],
    ["SECURITY", "A new advisory needs triage", 133],
    ["PROVIDER STATUS", "The operating context moved", 161],
  ];
  return (
    <AbsoluteFill style={{ background: `radial-gradient(circle at 84% 18%, #214c3e 0, ${INK} 42%, #0c1715 100%)`, color: "white", fontFamily: "Inter Variable, Inter, sans-serif" }}>
      <div style={{ position: "absolute", left: 76, top: 58 }}><Logo light size={38} /></div>
      <div style={{ position: "absolute", right: 76, top: 68, color: "#8ca69b", fontSize: 15, letterSpacing: 1.8 }}>JUNCTION 2026 · CONTEXT.DEV</div>
      <div style={{ position: "absolute", left: 96, top: 235, width: 920, opacity: title, transform: `translateY(${(1 - title) * 30}px)` }}>
        <Kicker light>Release evidence, continuously</Kicker>
        <div style={{ marginTop: 28, fontSize: 86, lineHeight: 1.04, fontWeight: 730, letterSpacing: -4.5 }}>Approved is a moment.</div>
        <div style={{ marginTop: 12, color: MINT_LIGHT, fontSize: 86, lineHeight: 1.04, fontWeight: 730, letterSpacing: -4.5 }}>Risk keeps moving.</div>
        <div style={{ marginTop: 34, color: "#aac0b6", fontSize: 30, lineHeight: 1.5, maxWidth: 760 }}>DriftCI connects your release timeline to the world around it.</div>
      </div>
      <div style={{ position: "absolute", right: 100, top: 205, width: 570, borderRadius: 22, padding: 30, background: "#f8faf5", color: INK, boxShadow: "0 30px 90px rgba(0,0,0,.32)", ...entrance(frame, 18, 24) }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ color: MUTED, fontSize: 14, fontWeight: 750, letterSpacing: 1.7 }}>PULL REQUEST</span>
          <span style={{ padding: "6px 10px", borderRadius: 7, background: MINT_SOFT, color: "#127353", fontSize: 13, fontWeight: 700 }}>SNAPSHOT</span>
        </div>
        <div style={{ marginTop: 28, fontSize: 27, fontWeight: 680, letterSpacing: -0.8 }}>main ← feature/provider-update</div>
        <div style={{ marginTop: 30, display: "grid", gap: 15 }}>
          {[["✓", "Review approved", "GitHub review"], ["✓", "Checks passed", "Observed CI"], ["#", "Head 8fa2…c91d", "Exact commit"]].map(([icon, label, detail]) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 14, padding: "13px 15px", borderRadius: 11, background: "#edf2ea" }}>
              <span style={{ width: 28, height: 28, borderRadius: 20, display: "grid", placeItems: "center", color: "#0f6949", background: "#cdeadb", fontWeight: 800 }}>{icon}</span>
              <strong style={{ fontSize: 19 }}>{label}</strong><span style={{ marginLeft: "auto", color: MUTED, fontSize: 14 }}>{detail}</span>
            </div>
          ))}
        </div>
      </div>
      <div style={{ position: "absolute", right: 115, top: 650, width: 580, display: "grid", gap: 12 }}>
        {alerts.map(([type, text, start], index) => (
          <div key={type} style={{ ...entrance(frame, Number(start)), display: "flex", alignItems: "center", gap: 16, padding: "14px 18px", border: "1px solid rgba(227,101,83,.42)", borderRadius: 12, background: "rgba(50,28,25,.9)", boxShadow: "0 12px 35px rgba(0,0,0,.18)", transform: `translateX(${(1 - reveal(frame, Number(start))) * (60 + index * 15)}px)` }}>
            <span style={{ width: 9, height: 9, borderRadius: 10, background: CORAL, boxShadow: "0 0 0 5px rgba(227,101,83,.12)" }} />
            <div><div style={{ color: "#f1a598", fontSize: 11, fontWeight: 800, letterSpacing: 1.4 }}>{type}</div><div style={{ marginTop: 3, fontSize: 16, color: "#f7eeeb" }}>{text}</div></div>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const Problem = () => {
  const frame = useCurrentFrame();
  const cards = [
    ["GITHUB", "Review approved", "09:41", "✓", MINT],
    ["CI", "Checks passed", "09:44", "✓", MINT],
    ["OFFICIAL WEB", "Lifecycle changed", "09:46", "!", CORAL],
    ["SECURITY", "Advisory published", "09:47", "!", CORAL],
  ];
  return (
    <AbsoluteFill style={{ background: PAPER, color: INK, fontFamily: "Inter Variable, Inter, sans-serif" }}>
      <SceneHeading kicker="The coordination tax" title="Release work lives in the gaps." />
      <div style={{ position: "absolute", left: 100, right: 100, top: 276, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 24 }}>
        {cards.map(([source, status, time, icon, color], index) => (
          <div key={source} style={{ ...entrance(frame, 8 + index * 17), position: "relative", minHeight: 250, padding: 28, borderRadius: 18, background: SURFACE, border: "1px solid #dce2d8", boxShadow: "0 12px 35px rgba(25,43,36,.06)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}><span style={{ color: MUTED, fontSize: 13, fontWeight: 760, letterSpacing: 1.5 }}>{source}</span><span style={{ width: 32, height: 32, display: "grid", placeItems: "center", borderRadius: 20, color, background: color === MINT ? MINT_SOFT : CORAL_SOFT, fontSize: 20, fontWeight: 800 }}>{icon}</span></div>
            <div style={{ marginTop: 38, fontSize: 28, fontWeight: 680, letterSpacing: -0.8 }}>{status}</div>
            <div style={{ marginTop: 13, color: color, fontSize: 30, fontFamily: "monospace", fontWeight: 700 }}>{time}</div>
            <div style={{ position: "absolute", left: 28, right: 28, bottom: 24, height: 4, borderRadius: 4, background: "#edf0e9" }}><div style={{ width: `${35 + index * 19}%`, height: "100%", borderRadius: 4, background: color, opacity: 0.65 }} /></div>
          </div>
        ))}
      </div>
      <div style={{ position: "absolute", left: 110, right: 110, top: 557, height: 2, background: `linear-gradient(90deg, ${MINT} 0 48%, ${CORAL} 48% 100%)`, opacity: reveal(frame, 75, 35) }} />
      <div style={{ position: "absolute", left: 180, right: 180, top: 650, textAlign: "center", ...entrance(frame, 98, 24) }}>
        <div style={{ color: INK, fontSize: 46, fontWeight: 690, letterSpacing: -1.7 }}>What changed? What matters? Who acts next?</div>
        <div style={{ marginTop: 18, color: MUTED, fontSize: 25 }}>Four systems. Four timestamps. One release to coordinate.</div>
      </div>
    </AbsoluteFill>
  );
};

const Manager = () => {
  const frame = useCurrentFrame();
  const work = [
    ["01", "Review external evidence", "Source receipt · matched files · observation time", "NEEDS REVIEW", CORAL],
    ["02", "Work vulnerability response", "Affected version · reachability clue · checklist", "RESPONSE", AMBER],
    ["03", "Revisit an expired decision", "New head, CI result or evidence fingerprint", "STALE", CORAL],
  ];
  return (
    <AbsoluteFill style={{ background: `linear-gradient(135deg, ${INK}, #102923)`, color: "white", fontFamily: "Inter Variable, Inter, sans-serif" }}>
      <SceneHeading kicker="Automatic project management" title="From movement in the world to the next action." light right={<div style={{ color: "#829e91", fontSize: 16, paddingBottom: 8 }}>CHANGE → EVIDENCE → WORK</div>} />
      <div style={{ position: "absolute", left: 82, top: 258, width: 480 }}>
        <div style={{ color: "#79958a", fontSize: 13, fontWeight: 750, letterSpacing: 2 }}>CONTINUOUS INPUTS</div>
        {[["GitHub", "PRs · reviews · checks"], ["Official web", "Lifecycle · pricing · releases · status"], ["Security intelligence", "OSV · CISA KEV"]].map(([name, detail], index) => (
          <div key={name} style={{ ...entrance(frame, 10 + index * 18), marginTop: 20, padding: "22px 24px", borderRadius: 14, background: "rgba(255,255,255,.055)", border: "1px solid rgba(151,190,172,.16)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}><span style={{ width: 9, height: 9, borderRadius: 10, background: MINT }} /><strong style={{ fontSize: 23 }}>{name}</strong></div>
            <div style={{ margin: "8px 0 0 21px", color: "#98b0a5", fontSize: 17 }}>{detail}</div>
          </div>
        ))}
      </div>
      <div style={{ position: "absolute", left: 585, top: 420, color: MINT_LIGHT, fontSize: 60, opacity: reveal(frame, 65) }}>→</div>
      <div style={{ position: "absolute", left: 690, right: 80, top: 246 }}>
        <div style={{ color: "#79958a", fontSize: 13, fontWeight: 750, letterSpacing: 2 }}>DRIFTCI WORK QUEUE</div>
        {work.map(([number, title, detail, status, color], index) => (
          <div key={number} style={{ ...entrance(frame, 50 + index * 48), display: "flex", alignItems: "center", gap: 22, marginTop: 18, padding: "22px 24px", borderRadius: 15, background: "#f7f9f4", color: INK, boxShadow: "0 12px 35px rgba(0,0,0,.15)" }}>
            <div style={{ color: "#91a199", fontSize: 18, fontFamily: "monospace" }}>{number}</div>
            <div style={{ flex: 1 }}><div style={{ fontSize: 25, fontWeight: 690, letterSpacing: -0.6 }}>{title}</div><div style={{ marginTop: 7, color: MUTED, fontSize: 16 }}>{detail}</div></div>
            <div style={{ padding: "7px 10px", borderRadius: 7, background: color === AMBER ? "#f8efd9" : CORAL_SOFT, color: color === AMBER ? "#886018" : "#a33c30", fontSize: 11, fontWeight: 800, letterSpacing: 0.8 }}>{status}</div>
          </div>
        ))}
      </div>
      <div style={{ position: "absolute", left: 690, right: 80, top: 702, display: "flex", alignItems: "center", gap: 18, padding: "19px 24px", borderRadius: 12, color: MINT_LIGHT, background: "rgba(41,184,135,.09)", border: "1px solid rgba(124,224,185,.2)", fontSize: 19, ...entrance(frame, 190) }}>
        <span style={{ width: 10, height: 10, borderRadius: 10, background: MINT_LIGHT, boxShadow: "0 0 0 6px rgba(124,224,185,.09)" }} />One durable live timeline · replayable events · baselines kept distinct
      </div>
    </AbsoluteFill>
  );
};

const Vulnerability = () => {
  const frame = useCurrentFrame();
  const steps = [
    ["01", "Confirm the affected version", "Package, installed version and fixed-version guidance"],
    ["02", "Assess repository clues", "Relevant locations with uncertainty kept visible"],
    ["03", "Work the ordered checklist", "Timestamped response steps and retained history"],
    ["04", "Export the incident record", "A portable Markdown handoff with source receipts"],
  ];
  return (
    <AbsoluteFill style={{ background: INK, color: "white", fontFamily: "Inter Variable, Inter, sans-serif" }}>
      <SceneHeading kicker="Vulnerability auditor" title="Work the incident, not just the CVE." light right={<div style={{ color: "#93aa9f", fontSize: 16, paddingBottom: 8 }}>OSV + CISA KEV + REPOSITORY EVIDENCE</div>} />
      <div style={{ position: "absolute", left: 70, top: 211, width: 1030, height: 680, borderRadius: 18, overflow: "hidden", border: "1px solid #365148", boxShadow: "0 22px 60px rgba(0,0,0,.28)", ...entrance(frame, 5) }}>
        <AppFrame shot="vulnerabilities" pan={120} />
      </div>
      <div style={{ position: "absolute", left: 1140, right: 65, top: 218 }}>
        <div style={{ color: MINT_LIGHT, fontSize: 13, fontWeight: 750, letterSpacing: 1.8 }}>FROM ADVISORY TO RESPONSE</div>
        {steps.map(([number, title, detail], index) => (
          <div key={number} style={{ ...entrance(frame, 35 + index * 62), display: "flex", gap: 17, marginTop: 22 }}>
            <div style={{ flex: "0 0 auto", width: 42, height: 42, display: "grid", placeItems: "center", borderRadius: 12, color: MINT_LIGHT, background: "rgba(41,184,135,.12)", border: "1px solid rgba(124,224,185,.2)", fontSize: 14, fontFamily: "monospace" }}>{number}</div>
            <div><div style={{ fontSize: 22, fontWeight: 650, letterSpacing: -0.4 }}>{title}</div><div style={{ marginTop: 5, maxWidth: 570, color: "#91a99e", fontSize: 15, lineHeight: 1.45 }}>{detail}</div></div>
          </div>
        ))}
        <div style={{ ...entrance(frame, 275), marginTop: 28, padding: "15px 18px", borderRadius: 10, background: "rgba(213,155,60,.11)", border: "1px solid rgba(213,155,60,.25)", color: "#ebc889", fontSize: 16 }}>
          Reachability clues ≠ proof of exploitability
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Decision = () => {
  const frame = useCurrentFrame();
  const triggers = ["New commit", "New CI result", "New external fact"];
  return (
    <AbsoluteFill style={{ background: PAPER, color: INK, fontFamily: "Inter Variable, Inter, sans-serif" }}>
      <SceneHeading kicker="Accountable automation" title="A decision with an expiration date." right={<div style={{ color: MUTED, fontSize: 15, paddingBottom: 8 }}>EXACT HEAD · EXACT EVIDENCE · NAMED OWNER</div>} />
      <div style={{ position: "absolute", left: 72, top: 215, width: 665, height: 565, padding: 30, borderRadius: 19, background: INK, color: "white", boxShadow: "0 18px 50px rgba(20,37,31,.18)", ...entrance(frame, 8) }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><span style={{ color: MINT_LIGHT, fontSize: 13, fontWeight: 750, letterSpacing: 1.8 }}>DECISION SCOPE</span><span style={{ padding: "6px 10px", borderRadius: 7, color: "#efc67e", background: "rgba(213,155,60,.12)", fontSize: 12, fontWeight: 700 }}>LOCAL QA HOLD</span></div>
        <div style={{ marginTop: 26, display: "grid", gap: 13 }}>
          {[["HEAD COMMIT", "18585a15"], ["EVIDENCE HASH", "4f53cda1"], ["CI SNAPSHOT", "Observed check runs"], ["DECISION OWNER", "DriftCI browser QA"]].map(([label, value]) => (
            <div key={label} style={{ display: "flex", alignItems: "center", padding: "14px 16px", borderRadius: 10, background: "rgba(255,255,255,.055)", border: "1px solid rgba(151,190,172,.13)" }}><span style={{ color: "#8fa99c", fontSize: 12, fontWeight: 720, letterSpacing: 1 }}>{label}</span><code style={{ marginLeft: "auto", color: "#eef7f0", fontSize: 18 }}>{value}</code></div>
          ))}
        </div>
        <div style={{ marginTop: 19, color: "#88a296", fontSize: 14, lineHeight: 1.5 }}>Actual public-demo QA record. Local DriftCI decisions remain separate from GitHub approvals.</div>
      </div>
      <div style={{ position: "absolute", left: 766, right: 70, top: 215, height: 565, borderRadius: 19, overflow: "hidden", border: "1px solid #d4dbd0", boxShadow: "0 18px 50px rgba(20,37,31,.12)", ...entrance(frame, 18) }}>
        <AppFrame shot="release-decision" pan={55} />
      </div>
      <div style={{ position: "absolute", left: 130, right: 130, top: 815, display: "flex", alignItems: "center", justifyContent: "center", gap: 14, ...entrance(frame, 210) }}>
        {triggers.map((trigger) => <div key={trigger} style={{ padding: "13px 18px", borderRadius: 10, color: "#7c4439", background: CORAL_SOFT, border: "1px solid #f0cfc6", fontSize: 18, fontWeight: 650 }}>{trigger}</div>)}
        <div style={{ color: CORAL, fontSize: 30 }}>→</div>
        <div style={{ padding: "14px 22px", borderRadius: 10, color: "white", background: CORAL, fontSize: 18, fontWeight: 760, letterSpacing: 0.4 }}>DECISION EXPIRED · REVIEW AGAIN</div>
      </div>
    </AbsoluteFill>
  );
};

const Close = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({ frame, fps, config: { damping: 18, stiffness: 80 } });
  return (
    <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 20%, #214b3d 0, ${INK} 48%, #0b1714 100%)`, color: "white", fontFamily: "Inter Variable, Inter, sans-serif", alignItems: "center" }}>
      <div style={{ marginTop: 170, opacity: progress, transform: `scale(${0.9 + 0.1 * progress})` }}><Logo light size={112} /></div>
      <div style={{ marginTop: 66, color: "#f5faf6", fontSize: 58, fontWeight: 670, letterSpacing: -2.2, ...entrance(frame, 15, 24) }}>Ship with evidence that is still true.</div>
      <div style={{ marginTop: 24, color: "#a1b9ad", fontSize: 27, ...entrance(frame, 35, 24) }}>Automatic release project management · Vulnerability response</div>
      <div style={{ marginTop: 58, display: "flex", gap: 14, ...entrance(frame, 50) }}>
        {["GitHub", "Context.dev", "OSV", "CISA KEV"].map((name) => <div key={name} style={{ padding: "12px 20px", borderRadius: 10, color: MINT_LIGHT, background: "rgba(41,184,135,.09)", border: "1px solid rgba(124,224,185,.2)", fontSize: 19, fontWeight: 620 }}>{name}</div>)}
      </div>
      <div style={{ marginTop: 62, padding: "15px 25px", borderRadius: 12, background: "#f2f7f1", color: INK, fontSize: 23, fontWeight: 650, ...entrance(frame, 70) }}>driftci.ajc.contexio.fi</div>
      <div style={{ position: "absolute", top: 55, left: 70, color: "#718f81", fontSize: 14, letterSpacing: 1.6 }}>JUNCTION 2026</div>
      <div style={{ position: "absolute", top: 55, right: 70, color: "#718f81", fontSize: 14, letterSpacing: 1.6 }}>THE WEB, WATCHED</div>
    </AbsoluteFill>
  );
};

export const DriftCI = () => {
  let from = 0;
  return (
    <AbsoluteFill style={{ background: INK }}>
      <Audio src={staticFile("music.wav")} volume={0.07} />
      {scenes.map((scene, index) => {
        const duration = Math.round(scene.sec * FPS);
        const start = from;
        from += duration;
        return (
          <Sequence key={scene.id} from={start} durationInFrames={duration}>
            {scene.id === "hook" && <Hook />}
            {scene.id === "problem" && <Problem />}
            {scene.id === "release" && <ShotScene shot="release-room" kicker="Automatic release project manager" title="One release room. Every current fact." chips={["Exact PR head", "Observed CI", "Official evidence"]} pan={155} />}
            {scene.id === "manager" && <Manager />}
            {scene.id === "watch" && <ShotScene shot="web-watch" kicker="Context.dev web intelligence" title="Watch the sources your software depends on." chips={["Snapshots", "Source receipts", "Before / after diffs"]} pan={215} />}
            {scene.id === "vulnerability" && <Vulnerability />}
            {scene.id === "decision" && <Decision />}
            {scene.id === "close" && <Close />}
            <Sequence from={index === 0 ? 18 : 6}><Audio src={staticFile(scene.vo)} /></Sequence>
            <Caption text={scene.say} duration={duration} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
