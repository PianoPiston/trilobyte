// Captures 1920x1080 stills and short frame sequences of the Trilobyte editor (http://127.0.0.1:5175) into public/cap/.
// Usage: node scripts/capture.mjs [name-filter]
import { mkdirSync } from "node:fs";
import { chromium } from "/home/user/junction/app/tests/e2e/node_modules/playwright/index.mjs";

const BASE = process.env.APP_URL || "http://127.0.0.1:5175", OUT = "public/cap";
const PLAN = process.env.PLAN || "/tmp/tvid/floor-plan.png";
const SW = "swiss_dwellings~site3634_bldg5596_floor24203", UP = process.env.UP || "upload~b3950bedeae8";
mkdirSync(OUT, { recursive: true });
const b = await chromium.launch({ executablePath: "/usr/lib64/chromium-browser/headless_shell", args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1.2 });
const shot = async (name, wait = 1000) => { await p.waitForTimeout(wait); await p.screenshot({ path: `${OUT}/${name}.png` }); console.log("shot", name); };
const open = async (id) => { await p.goto(`${BASE}/d/${encodeURIComponent(id)}`); await p.waitForSelector(".figures", { timeout: 180000 }); await p.waitForTimeout(1200); };
const ask = async (q, frames) => {
  const inp = p.locator(".ask input"); await inp.click();
  for (let i = 0; i < q.length; i++) { await inp.press(q[i] === " " ? "Space" : q[i]); if (frames && i % 2 === 1) await shot(`${frames}-${String(i >> 1).padStart(3, "0")}`, 0); }
  await p.click(".ask-row button"); await p.waitForSelector(".answer-card:not(.loading-card)", { timeout: 120000 });
};
// orbit the 3D model by dragging, one still per step
const orbit = async (name, n, dx) => {
  await p.click(".mode button:nth-child(2)"); await p.waitForSelector(".scene3d canvas"); await p.waitForTimeout(3000);
  const box = await p.locator(".scene3d canvas").boundingBox(); let x = box.x + box.width * 0.4; const y = box.y + box.height * 0.5;
  await p.mouse.move(x, y); await p.mouse.down();
  for (let i = 0; i < n; i++) { x += dx; await p.mouse.move(x, y, { steps: 2 }); await shot(`${name}-${String(i).padStart(3, "0")}`, 60); }
  await p.mouse.up();
};
const steps = {
  home: async () => { await p.goto(BASE + "/"); await p.waitForSelector(".dropzone"); await shot("home"); },
  drop: async () => {
    await p.goto(BASE + "/"); await p.waitForSelector(".dropzone");
    await p.setInputFiles("input[type=file]", PLAN); await shot("uploading", 1200);
    await p.waitForURL(/\/d\//, { timeout: 180000 }); await p.waitForSelector(".figures", { timeout: 180000 }); await shot("up-summary", 1500);
    console.log("upload id", decodeURIComponent(p.url().split("/d/")[1]));
  },
  upconcrete: async () => { await open(UP); await p.click(".examples button:first-child"); await p.waitForSelector(".answer-card:not(.loading-card)"); await shot("up-concrete", 1500); },
  up3d: async () => { await open(UP); await orbit("up3d", 60, 7); },
  swsummary: async () => { await open(SW); await shot("sw-summary"); },
  swask: async () => { await open(SW); await ask("How much concrete do I need for this floor?"); await shot("sw-concrete", 1500); },
  swmat: async () => {
    await open(SW); await p.click(".tabs button:nth-child(2)"); await p.waitForSelector(".bom"); await shot("sw-materials");
    await p.locator(".tab-body").evaluate((e) => e.scrollBy(0, 520)); await shot("sw-materials-2");
  },
  swroom: async () => {
    await open(SW); await p.click("table.rooms tbody tr:nth-child(2)"); await p.click(".tabs button:nth-child(2)"); await p.waitForSelector(".bom"); await shot("sw-room-price");
  },
  swkitchen: async () => { await open(SW); await ask("How much laminate do I need for the kitchens, and what does it cost?", "sw-type"); await shot("sw-kitchen", 1500); },
  measure: async () => {
    await open(UP); const v = await p.locator(".sheet").boundingBox();
    await p.click(".toolbar button:nth-child(2)"); await p.mouse.click(v.x + 260, v.y + 330); await p.mouse.click(v.x + 640, v.y + 330); await shot("measure-distance");
    await p.click(".toolbar button:nth-child(3)");
    for (const [x, y] of [[300, 420], [560, 420], [560, 640], [300, 640], [300, 420]]) await p.mouse.click(v.x + x, v.y + y);
    await shot("measure-area");
  },
  sw3d: async () => { await open(SW); await orbit("sw3d", 60, 8); },
};
const only = process.argv[2];
for (const [name, fn] of Object.entries(steps)) {
  if (only && !name.includes(only)) continue;
  try { await fn(); } catch (e) { console.log("FAIL", name, String(e).slice(0, 300)); }
}
await b.close();
