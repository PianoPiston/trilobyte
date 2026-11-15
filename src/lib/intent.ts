// Recognises material and cost questions so they are answered from the measured plan and live prices
import { roomName } from "./takeoff";
import type { Room } from "./takeoff";

const MATERIALS: [string, RegExp][] = [
  ["concrete", /concrete|betoni|slab|laatta|valu/],
  ["screed", /screed|levell?ing|tasoite/],
  ["flooring", /flooring|laminate|laminaatti|parquet|parketti|lattiamateriaali/],
  ["plasterboard", /plasterboard|drywall|gypsum|kipsi/],
  ["paint", /paint|maali/],
  ["skirting", /skirting|baseboard|jalkalista/],
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

export type Intent = { material: string | null; rooms: Room[] | null; scope: string };

export function materialIntent(q: string, rooms: Room[]): Intent | null {
  const s = q.toLowerCase();
  const material = MATERIALS.find(([, re]) => re.test(s))?.[0] ?? null;
  if (!material && !ANY.test(s)) return null;
  // an exact room name or number ("Küche 3.06", "3.06") wins over a room type ("kitchens")
  const exact = rooms.filter((r) => r.name && (s.includes(roomName(r).toLowerCase()) || / \d+\.\d+$/.test(r.name) && s.includes(r.name.split(" ").pop()!)));
  if (exact.length) return { material, rooms: exact, scope: exact.map(roomName).join(", ") };
  for (const [word, nameRe] of ROOM_WORDS) {
    if (!word.test(s)) continue;
    const hit = rooms.filter((r) => r.name && nameRe.test(r.name));
    if (hit.length) return { material, rooms: hit, scope: hit.length === 1 ? roomName(hit[0]) : `${hit.length} rooms: ${hit.map(roomName).join(", ")}` };
  }
  return { material, rooms: null, scope: "the whole floor" };
}
