// Captures demo screenshots from the running app (http://127.0.0.1:8090) into public/shots/.
import puppeteer from "puppeteer-core";
const BASE = process.env.APP_URL || "http://127.0.0.1:8090";
const CHROME = "node_modules/.remotion/chrome-headless-shell/linux64/chrome-headless-shell-linux64/chrome-headless-shell";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await puppeteer.launch({ executablePath: CHROME, args: ["--no-sandbox"], defaultViewport: { width: 1920, height: 1080, deviceScaleFactor: 1 } });
const page = await browser.newPage();
async function shot(name) { await sleep(800); await page.screenshot({ path: `public/shots/${name}.png` }); console.log("shot", name); }
async function open(path) { await page.goto(BASE + path, { waitUntil: "networkidle0", timeout: 120000 }); await sleep(1500); }
async function ask(q) {
  const inp = await page.waitForSelector('input[aria-label="Question"]');
  await inp.click({ clickCount: 3 }); await inp.type(q, { delay: 10 }); await page.keyboard.press("Enter");
  await page.waitForFunction(() => { const b = document.querySelector("form.ask button[type=submit]"); return b && b.textContent !== "…" && document.querySelector(".answer-card"); }, { timeout: 180000 });
  await sleep(1500);
}
async function toggle(label) {
  await page.evaluate((label) => { for (const l of document.querySelectorAll("label")) if (l.textContent.includes(label)) { const i = l.querySelector("input"); if (i && !i.checked) i.click(); } }, label);
  await sleep(2500);
}
const shots = [
  ["01-home", "/", null],
  ["02-swiss-bedrooms", "/d/swiss_dwellings~site3634_bldg5596_floor24203", "How many rooms labelled 'Schlafzimmer' are there on this floor?"],
  ["03-swiss-area", "/d/swiss_dwellings~site3634_bldg5596_floor24203", "What is the total floor area of all apartments on this floor in m²?"],
  ["04-cubicasa-bedrooms", "/d/cubicasa5k~colorful-12981", "How many bedrooms (makuuhuone, usually marked MH) are on this floor plan?"],
  ["05-cubicasa-windows", "/d/cubicasa5k~colorful-12981", "Kuinka monta ikkunaa pohjapiirustuksessa on?"],
  ["06-upload-detections", "/d/upload~ddbad24db0e8", "How many doors are shown on this floor plan? Count doorways fitted with a door; open doorways without a door leaf do not count."],
];
for (const [name, path, q] of shots) {
  try {
    await open(path);
    if (name === "05-cubicasa-windows") await toggle("Text layer");
    if (name === "06-upload-detections") await toggle("Standardized layer");
    if (q) await ask(q);
    await shot(name);
  } catch (e) { console.log("FAILED", name, e.message.slice(0, 120)); }
}
// IFC + historic: pick the first drawing of each from the catalog
const cat = await (await fetch(BASE + "/api/drawings")).json();
const ifc = cat.drawings.find((d) => d.source === "ifc_models");
const hist = cat.drawings.find((d) => d.source === "finna") || cat.drawings.find((d) => d.track === "historic");
try { await open(`/d/${encodeURIComponent(ifc.id)}`); await ask("How many doors are there in this building model?"); await shot("07-ifc"); } catch (e) { console.log("FAILED ifc", e.message.slice(0, 120)); }
try {
  await open(`/d/${encodeURIComponent(hist.id)}`); await ask("Which building is shown in this drawing, and when was it drawn?");
  await page.evaluate(() => { for (const b of document.querySelectorAll("button")) if (b.textContent.startsWith("Context")) b.click(); });
  await shot("08-historic");
} catch (e) { console.log("FAILED historic", e.message.slice(0, 120)); }
try { await open("/benchmark"); await shot("09-benchmark"); } catch (e) { console.log("FAILED bench", e.message.slice(0, 120)); }
await browser.close();
