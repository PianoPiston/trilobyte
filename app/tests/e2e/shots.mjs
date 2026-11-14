// Screenshot tour of the demo UI: node shots.mjs [baseUrl] [outDir]
import { chromium } from "playwright";
const base = process.argv[2] || "http://127.0.0.1:8090";
const out = process.argv[3] || "../../../artifacts/screenshots";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const errs = [];
p.on("pageerror", (e) => errs.push(String(e)));
p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
const shot = async (name) => { await p.waitForTimeout(900); await p.screenshot({ path: `${out}/${name}.png` }); console.log("shot", name); };
await p.goto(base + "/"); await p.waitForSelector(".card"); await shot("01-browse");
const ask = async (id, q, name) => {
  await p.goto(`${base}/d/${encodeURIComponent(id)}`); await p.waitForSelector(".ask input");
  await p.fill(".ask input", q); await p.click(".ask-row button"); await p.waitForSelector(".answer-card:not(.loading-card)", { timeout: 60000 });
  await shot(name);
};
await ask("swiss_dwellings~site3634_bldg5596_floor24203", "How many rooms labelled 'Schlafzimmer' are there on this floor?", "02-swiss-bedrooms");
await ask("swiss_dwellings~site3634_bldg5596_floor24203", "What is the total area of apartment A in m²?", "03-swiss-area");
await ask("ifc_models~kit-fzk-haus_ac20-fzk-haus_plan-01-erdgeschoss", "How many windows are shown on the floor plan of 'Erdgeschoss'?", "04-ifc-windows");
await ask("cubicasa5k~high_quality-12130", "Kuinka monta saunaa pohjapiirustuksessa on?", "05-cubicasa-fi");
await ask("finna~hka.139879309684900_166878548098200", "In what year was this drawing made?", "06-historic");
await p.goto(base + "/search?q=3%20bedrooms%20and%20a%20sauna"); await p.waitForSelector(".result"); await shot("07-search");
await p.goto(base + "/benchmark"); await p.waitForSelector(".chart"); await shot("08-benchmark");
await p.goto(base + "/developers"); await shot("09-developers");
console.log("errors:", errs.length ? errs : "none");
await b.close();
