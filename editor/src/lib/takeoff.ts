// Measurements and material quantities derived from the takeoff service (/x/takeoff, /x/prices)
export type Room = {
  id: string; name?: string | null; polygon: number[][]; area_px: number; perimeter_px: number;
  area_m2?: number | null; printed_area_m2?: number | null; outdoor?: boolean; shaft?: boolean;
};
export type Opening = { id: string; bbox: number[]; width_px: number };
export type Takeoff = {
  id: string; image_size: [number, number]; source: "cad" | "bim" | "segmented";
  rooms: Room[]; doors: Opening[]; windows: Opening[]; walls: number[][];
  scale: { m_per_px: number | null; method: string; confidence: number };
};
export type PriceSource = { price: number; quote: string; url: string; title: string };
export type Price = {
  key: string; label: string; unit: string; live: boolean; price: number;
  low?: number; high?: number; n?: number; sources?: PriceSource[]; note?: string;
};
export type Prices = { fetched_at: string | null; refreshing: boolean; items: Price[] };
export type Assumptions = { slabCm: number; wallHeight: number; wastePct: number };
export type Line = { key: string; label: string; qty: number; unit: string; basis: string };

export const DEFAULTS: Assumptions = { slabCm: 20, wallHeight: 2.6, wastePct: 5 };
export const UNIT: Record<string, string> = { m3: "m³", m2: "m²", l: "l", kg: "kg", m: "m", pcs: "pcs" };

async function j<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
export const fetchTakeoff = (id: string) => j<Takeoff>(`/x/takeoff/${encodeURIComponent(id)}`);
export const fetchPrices = (refresh = false) => j<Prices>(`/x/prices${refresh ? "?refresh=1" : ""}`);

// Exact CAD/BIM area first, then the area printed on the drawing, then the measured polygon
export const roomArea = (r: Room, m: number) => r.area_m2 ?? r.printed_area_m2 ?? r.area_px * m * m;
export const measuredArea = (r: Room, m: number) => r.area_m2 ?? r.area_px * m * m;
export const roomPerimeter = (r: Room, m: number) => r.perimeter_px * m;
export const roomName = (r: Room) => r.name || `Room ${r.id.replace(/^S/, "")}`;
export const fmt = (v: number, digits = 1) => v.toLocaleString("en", { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const eur = (v: number) => "€" + v.toLocaleString("en", { minimumFractionDigits: v < 100 ? 2 : 0, maximumFractionDigits: v < 100 ? 2 : 0 });

export function centroid(p: number[][]): number[] {
  return [p.reduce((s, q) => s + q[0], 0) / p.length, p.reduce((s, q) => s + q[1], 0) / p.length];
}
export function polygonArea(p: number[][]): number {
  return Math.abs(p.reduce((s, q, i) => s + q[0] * p[(i + 1) % p.length][1] - p[(i + 1) % p.length][0] * q[1], 0)) / 2;
}

export type Totals = { rooms: Room[]; floor: number; indoor: number; perimeter: number; wallArea: number; doors: number; windows: number };

// Quantities for a set of rooms, or for the whole floor when rooms is null
export function totals(t: Takeoff, m: number, a: Assumptions, subset: Room[] | null): Totals {
  const rooms = (subset ?? t.rooms).filter((r) => !r.shaft);
  const floor = rooms.reduce((s, r) => s + roomArea(r, m), 0);
  const indoor = rooms.filter((r) => !r.outdoor).reduce((s, r) => s + roomArea(r, m), 0);
  const perimeter = rooms.filter((r) => !r.outdoor).reduce((s, r) => s + roomPerimeter(r, m), 0);
  // each door opens two wall faces and each window one; openings are attributed only at floor level
  const whole = subset === null;
  const doorArea = whole ? t.doors.reduce((s, d) => s + d.width_px * m * 2.1 * 2, 0) : 0;
  const windowArea = whole ? t.windows.reduce((s, w) => s + w.width_px * m * 1.2, 0) : 0;
  return { rooms, floor, indoor, perimeter, wallArea: Math.max(0, perimeter * a.wallHeight - doorArea - windowArea),
    doors: whole ? t.doors.length : 0, windows: whole ? t.windows.length : 0 };
}

const WET = /bath|\bwc\b|toilet|sauna|shower|wash|\bk?ph\b|\bbad\b|dusche|pesu|kylpy|wet/i;

export function materialLines(x: Totals, t: Takeoff, m: number, a: Assumptions, wholeFloor: boolean): Line[] {
  const w = 1 + a.wastePct / 100;
  const waste = a.wastePct ? ` + ${a.wastePct}% waste` : "";
  const doorWidth = wholeFloor ? t.doors.reduce((s, d) => s + d.width_px * m, 0) : 0;
  const wet = x.rooms.filter((r) => !r.outdoor && WET.test(r.name || "")).reduce((s, r) => s + roomArea(r, m), 0);
  const dry = Math.max(0, x.indoor - wet);
  const lines: Line[] = [
    { key: "concrete", label: "Concrete, floor slab", qty: x.floor * (a.slabCm / 100) * w, unit: "m3", basis: `${fmt(x.floor)} m² × ${a.slabCm} cm slab${waste}` },
    { key: "mesh", label: "Reinforcement mesh", qty: x.floor * 1.1 * w, unit: "m2", basis: `${fmt(x.floor)} m² slab + 10% lap${waste}` },
    { key: "insulation", label: "EPS insulation under slab", qty: x.floor * w, unit: "m2", basis: `${fmt(x.floor)} m² slab${waste}` },
    { key: "membrane", label: "Vapour barrier membrane", qty: x.indoor * 1.1 * w, unit: "m2", basis: `${fmt(x.indoor)} m² indoor floor + 10% lap${waste}` },
    { key: "screed", label: "Levelling compound", qty: x.indoor * 8.5 * w, unit: "kg", basis: `${fmt(x.indoor)} m² × 5 mm layer at 1.7 kg/m² per mm${waste}` },
    { key: "flooring", label: "Laminate flooring, dry rooms", qty: dry * w, unit: "m2", basis: `${fmt(dry)} m² indoor floor outside wet rooms${waste}` },
    { key: "tiles", label: "Floor tiles, wet rooms", qty: wet * w, unit: "m2", basis: wet ? `${fmt(wet)} m² of bathrooms, WCs and saunas${waste}` : "No room is named as a wet room" },
    { key: "plasterboard", label: "Plasterboard, wall faces", qty: x.wallArea * w, unit: "m2", basis: `${fmt(x.perimeter)} m of wall × ${a.wallHeight} m${wholeFloor ? " − openings" : ""}${waste}` },
    { key: "primer", label: "Primer, walls", qty: x.wallArea / 10, unit: "l", basis: `${fmt(x.wallArea)} m² × 1 coat at 10 m²/l` },
    { key: "paint", label: "Wall paint, two coats", qty: (x.wallArea * 2) / 8, unit: "l", basis: `${fmt(x.wallArea)} m² × 2 coats at 8 m²/l` },
    { key: "ceilingpaint", label: "Ceiling paint, two coats", qty: (x.indoor * 2) / 8, unit: "l", basis: `${fmt(x.indoor)} m² ceiling × 2 coats at 8 m²/l` },
    { key: "skirting", label: "Skirting board", qty: Math.max(0, x.perimeter - doorWidth) * w, unit: "m", basis: `${fmt(x.perimeter)} m perimeter${wholeFloor ? " − door openings" : ""}${waste}` },
    { key: "moulding", label: "Ceiling moulding", qty: x.perimeter * w, unit: "m", basis: `${fmt(x.perimeter)} m perimeter${waste}` },
  ];
  if (wholeFloor && t.doors.length) lines.push({ key: "doors", label: "Interior doors", qty: t.doors.length, unit: "pcs", basis: `${t.doors.length} doors on the plan` });
  return lines;
}
