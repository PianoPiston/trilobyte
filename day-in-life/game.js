const DRAWING = "swiss_dwellings~site3634_bldg5596_floor24203";
const visits = [
  { name: "Ykä", role: "Carpenter", question: "Hey boss! How many apartments are there supposed to be?", query: "How many apartments (residential units) are shown on this floor plan?", label: "apartments", spoken: "Four apartments" },
  { name: "Jorma", role: "Concrete worker", question: "Got a minute? How many bedrooms are on this floor?", query: "How many rooms labelled 'Schlafzimmer' are there on this floor?", label: "bedrooms", spoken: "Eight bedrooms" },
  { name: "Make", role: "Door fitter", question: "Boss, I need to order the doors. How many are there in this plan?", query: "How many doors (interior doors and entrance doors together) are drawn on this floor plan?", label: "doors", spoken: "Forty-seven doors" },
];
const $ = id => document.getElementById(id);
let stage = "title", visit = 0, answer = null, muted = false, spoken = -1, speechTimer;

const workerSvg = `<svg viewBox="0 0 300 520" aria-hidden="true"><defs>
<linearGradient id="vest" x2="1" y2="1"><stop stop-color="#f8bf20"/><stop offset="1" stop-color="#d47705"/></linearGradient>
<linearGradient id="hat" x2=".8" y2="1"><stop stop-color="#ffd44d"/><stop offset="1" stop-color="#db9008"/></linearGradient>
<linearGradient id="shirt" x2="1" y2="1"><stop stop-color="#344a59"/><stop offset="1" stop-color="#152834"/></linearGradient></defs>
<ellipse cx="156" cy="502" rx="118" ry="15" fill="#000" opacity=".2"/>
<path d="M48 267Q52 217 105 209l40-10 54 16q43 15 48 68l18 144-55 7-12-89 7 154H86l8-151-18 88-52-15z" fill="url(#shirt)" stroke="#0c1820" stroke-width="5"/>
<path d="M117 211l31 20 32-21 36 14-17 245H88l-7-244z" fill="url(#vest)" stroke="#684508" stroke-width="4"/>
<path d="M137 226l-7 241M172 226l7 241" stroke="#fff4a4" stroke-width="9" opacity=".9"/>
<path d="M93 314l104 5M90 389l109 5" stroke="#eff4d8" stroke-width="15" opacity=".85"/>
<path d="M105 329l92 4M102 403l90 5" stroke="#909a83" stroke-width="5" opacity=".8"/>
<path d="M119 202l-2-39 60-2-1 47-29 23z" fill="#c98454" stroke="#4b2b22" stroke-width="4"/>
<path d="M94 110q0-61 56-61 60 0 61 65l-8 55q-18 42-53 40-37-1-52-42z" fill="#d79a68" stroke="#3b271f" stroke-width="5"/>
<path d="M94 123l-13-4q-13 4-4 26l18 14M208 122l13-4q13 4 5 26l-19 15" fill="#c98354" stroke="#4b2b22" stroke-width="4"/>
<path d="M108 139q13-10 28 1M164 140q13-11 28 0" fill="none" stroke="#533528" stroke-width="6" stroke-linecap="round"/>
<circle cx="126" cy="142" r="3.5" fill="#172129"/><circle cx="179" cy="142" r="3.5" fill="#172129"/>
<path d="M151 142l-8 24 16 3" fill="none" stroke="#975d42" stroke-width="4" stroke-linecap="round"/>
<path d="M110 176q38-15 77 0-8 33-39 33-30-1-38-33" fill="#493227"/><path d="M128 179q20 7 42 0" fill="none" stroke="#d5b398" stroke-width="4" stroke-linecap="round"/>
<path d="M87 109q1-79 65-80 66 2 65 82z" fill="url(#hat)" stroke="#5c430f" stroke-width="5"/><path d="M145 30v66M105 46l15 52M190 48l-14 50" stroke="#ffe784" stroke-width="7" opacity=".55"/>
<path d="M72 107q77-24 159 0l-4 20q-79-15-151 0z" fill="#edaa15" stroke="#5c430f" stroke-width="5"/>
<path d="M217 260q35 9 36 45l14 107q1 29-30 31-23-3-27-28l-15-101" fill="#c98454" stroke="#3b271f" stroke-width="5"/>
<path d="M209 250q28-3 44 22l-2 49-42 4-17-48z" fill="#263c4b" stroke="#10232e" stroke-width="4"/>
<path d="M91 460l-5 35-55 3q-12-16 8-25l23-10M183 460l10 33 52 8q8-18-13-24l-23-13" fill="#17232a" stroke="#0d151a" stroke-width="5"/></svg>`;

function say(text) {
  if (muted || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const line = new SpeechSynthesisUtterance(text);
  line.lang = "en-GB"; line.pitch = .65; line.rate = .9;
  const voice = speechSynthesis.getVoices().find(v => v.lang.toLowerCase() === "en-gb") || speechSynthesis.getVoices().find(v => v.lang.toLowerCase().startsWith("en"));
  if (voice) line.voice = voice;
  speechSynthesis.speak(line);
}

function setStage(next) {
  stage = next;
  $("game").className = `game stage-${next}`;
  const playing = !["title", "done"].includes(next);
  for (const id of ["hud", "clock", "sound", "minimap"]) $(id).hidden = !playing;
  $("intro").hidden = next !== "title";
  $("complete").hidden = next !== "done";
  $("worker-line").hidden = next !== "office";
  $("manager-line").hidden = next !== "dismiss";
  $("use").hidden = next !== "office";
  $("monitor-help").hidden = next !== "monitor";
  $("desktop").hidden = next === "monitor";
  $("computer").hidden = next !== "monitor";
  if (playing) {
    const v = visits[visit];
    $("objective").textContent = next === "dismiss" ? "Problem solved." : next === "monitor" ? "Use Trilobyte to find the answer." : `${v.name} has a question.`;
    $("visit-count").textContent = `${visit + 1} / ${visits.length} · SITE MANAGER EDITION`;
    $("clock").querySelector("b").textContent = `TUE 08:${42 + visit * 7}`;
    $("speaker").textContent = `${v.name.toUpperCase()} · ${v.role.toUpperCase()}`;
    $("worker-question").textContent = v.question;
    $("manager-answer").textContent = `${v.spoken}. Now fuck off.`;
    $("next").textContent = visit === visits.length - 1 ? "Finish shift →" : "Next visitor →";
    if (next === "office" && spoken !== visit) {
      spoken = visit;
      clearTimeout(speechTimer);
      speechTimer = setTimeout(() => say(v.question), 850);
    }
  }
}

function resetAnswer() {
  answer = null;
  $("query").textContent = visits[visit].query;
  $("computer-heading").textContent = `${visits[visit].name} needs an answer.`;
  $("answer").hidden = true; $("answer").innerHTML = "";
  $("ask").hidden = false; $("loading").hidden = true; $("trust").hidden = false; $("error").textContent = "";
}

function begin() {
  visit = 0; spoken = -1;
  $("worker").className = "worker";
  $("worker").innerHTML = workerSvg + `<div class="worker-tag"><b>${visits[0].name}</b><span>${visits[0].role}</span></div>`;
  resetAnswer(); setStage("office");
}

$("start").onclick = begin;
$("restart").onclick = begin;
function useComputer() { if (stage === "office") setStage("monitor"); }
$("use").onclick = useComputer;
$("monitor").onclick = useComputer;

$("ask").onclick = async () => {
  $("ask").hidden = true; $("trust").hidden = true; $("loading").hidden = false; $("error").textContent = "";
  try {
    const response = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ drawing_id: DRAWING, question: visits[visit].query }) });
    if (!response.ok) throw new Error();
    answer = await response.json();
    const value = typeof answer.answer === "number" && !Number.isInteger(answer.answer) ? answer.answer.toFixed(2) : String(answer.answer);
    $("answer").innerHTML = `<span class="answer-badge">✓ EXACT FROM CAD</span><div class="answer-value">${value}<small>${visits[visit].label}</small></div><p>Found directly in the DXF geometry. Evidence is attached to the answer.</p><div class="proof"><span>Ground-truth grade</span><span>${answer.evidence.length} evidence regions</span><span>${answer.latency_ms} ms</span></div><button id="tell" class="primary">Tell ${visits[visit].name} <kbd>↵</kbd></button>`;
    $("answer").hidden = false;
    $("tell").onclick = tell;
  } catch {
    $("error").textContent = "The drawing service did not respond. Check the API and try again.";
    $("ask").hidden = false; $("trust").hidden = false;
  } finally { $("loading").hidden = true; }
};

function tell() {
  if (!answer) return;
  setStage("dismiss");
  say(`${visits[visit].spoken}. Now fuck off.`);
}

$("next").onclick = () => {
  if (visit === visits.length - 1) { setStage("done"); return; }
  visit++; resetAnswer();
  $("worker").className = "worker";
  $("worker").innerHTML = workerSvg + `<div class="worker-tag"><b>${visits[visit].name}</b><span>${visits[visit].role}</span></div>`;
  setStage("office");
};

$("sound").onclick = () => {
  muted = !muted;
  speechSynthesis?.cancel();
  $("sound").textContent = muted ? "🔇 Voice off" : "🔊 Worker voice";
};

document.addEventListener("keydown", e => {
  if ((e.key === "e" || e.key === "E") && stage === "office") useComputer();
  if (e.key === "Enter" && stage === "monitor" && answer) tell();
  if (e.key === "Escape" && stage === "monitor") setStage("office");
});
window.addEventListener("beforeunload", () => speechSynthesis?.cancel());
