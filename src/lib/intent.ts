// Recognises room-count, floor-area and material questions so they are answered from the same measured rooms
// the Summary shows, instead of from a second, independent model
import { roomName } from "./takeoff";
import type { Room } from "./takeoff";

const MATERIALS: [string, RegExp][] = [
  ["mesh", /rebar|reinforc|mesh|raudoit|harjaterä/],
  ["insulation", /insulation|\beps\b|\bxps\b|eriste|styrox/],
  ["membrane", /vapou?r|membrane|höyrynsulku|muovi/],
  ["tiles", /tile|laatoi|lattialaatta|klinkkeri/],
  ["concrete", /concrete|betoni|slab|valu/],
  ["screed", /screed|levell?ing|tasoite/],
  ["flooring", /flooring|laminate|laminaatti|parquet|parketti|lattiamateriaali/],
  ["plasterboard", /plasterboard|drywall|gypsum|kipsi/],
  ["primer", /primer|pohjamaali/],
  ["ceilingpaint", /ceiling paint|kattomaali/],
  ["paint", /paint|maali/],
  ["moulding", /moulding|molding|cornice|kattolista/],
  ["skirting", /skirting|baseboard|jalkalista/],
  ["doors", /interior door|väliov|door.*(cost|price)/],
];
const ANY = /material|cost|price|budget|how much .*(need|order|buy|get)|kuinka paljon|hinta|maksaa|kustann/;

// Room name words in several languages, mapped to the English names used by the takeoff
const ROOM_WORDS: [RegExp, RegExp][] = [
  [/bedroom|makuuhuone|schlafzimmer/, /bedroom|schlafzimmer/i],
  [/kitchen|keittiö|küche|kueche/, /kitchen|küche/i],
  [/living|olohuone|wohnen/, /living|wohnen/i],
  [/bath|kylpy|\bbad\b/, /bath|\bbad\b/i],
  [/\bwc\b|toilet|vessa/, /\bwc\b|toilet/i],
  [/sauna/, /sauna/i],
  [/balcon|parveke|balkon/, /balcon|balkon/i],
  [/hall|corridor|eteinen|korridor/, /hall|korridor|corridor/i],
];

export type Intent = { kind: "count" | "area" | "material"; material: string | null; rooms: Room[] | null; scope: string };
const COUNT = /how many (rooms|spaces)\b|number of rooms|room count|montako huonetta|kuinka monta huonetta|wie viele (räume|zimmer)\b/;
const AREA = /\barea\b|square met|\bm2\b|m²|how big|pinta-ala|neliö|fläche/;

export function takeoffIntent(q: string, rooms: Room[]): Intent | null {
  const s = q.toLowerCase();
  // questions about labelled rooms ("rooms labelled 'Küche'") stay with the label-reading routes
  if (/label|['"‘’“”]/.test(s)) return null;
  const material = MATERIALS.find(([, re]) => re.test(s))?.[0] ?? null;
  const kind = material || ANY.test(s) ? "material" : COUNT.test(s) ? "count" : AREA.test(s) ? "area" : null;
  if (!kind) return null;
  // an exact room name or number ("Küche 3.06", "3.06") wins over a room type ("kitchens")
  const exact = rooms.filter((r) => r.name && (s.includes(roomName(r).toLowerCase()) || / \d+\.\d+$/.test(r.name) && s.includes(r.name.split(" ").pop()!)));
  if (exact.length) return { kind, material, rooms: exact, scope: exact.map(roomName).join(", ") };
  for (const [word, nameRe] of ROOM_WORDS) {
    if (!word.test(s)) continue;
    const hit = rooms.filter((r) => r.name && nameRe.test(r.name));
    if (hit.length) return { kind, material, rooms: hit, scope: hit.length === 1 ? roomName(hit[0]) : `${hit.length} rooms: ${hit.map(roomName).join(", ")}` };
  }
  // an area question about something we cannot resolve (a unit, a named zone) goes to the question routes
  if (kind === "area" && !/total|floor|whole|apartment|plan|kokonais|asunto/.test(s)) return null;
  return { kind, material, rooms: null, scope: "the whole floor" };
}
