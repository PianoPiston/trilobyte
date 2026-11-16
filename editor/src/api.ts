export type Shape = { polygon?: number[][]; bbox?: number[] };
export type Evidence = Shape & {
  id: string; label: string; kind?: string; element_id?: string | null; approximate?: boolean; off_sheet?: boolean;
};
export type Candidate = {
  rank: number; id: string; value: unknown; unit?: string | null; source: string; source_label?: string;
  confidence: number | null; evidence: Evidence[]; reason?: string | null; agree_with: string[];
};
export type Word = { text: string; bbox: number[]; conf?: number | null };
export type Answer = {
  drawing_id: string; question: string; answer: unknown; unit?: string | null;
  method: string; method_detail?: string; cached_method?: string | null;
  confidence: number | null; needs_check: boolean; needs_check_reasons: string[];
  evidence: Evidence[]; sources: { label: string; url?: string | null }[]; note?: string | null;
  cost_eur: number; latency_ms: number; route_trace: { route: string; result: string }[];
  ground_truth_eligible: boolean; suggested_answer?: unknown;
  ranked_candidates?: Candidate[]; decider?: string; judge?: { latency_s?: number } | null;
  reference?: { answer: unknown; unit?: string | null; match: boolean | null };
};
export type Example = { question: string; lang: string };
export type DrawingCard = {
  id: string; source: string; source_label: string; title: string; subtitle: string; formats: string[];
  split: string | null; seen_in_training: boolean | null; track: "modern" | "historic";
  licence: string | null; credit: string | null; source_url: string | null;
  image_size: [number, number]; teaser?: string[]; thumb_url: string; image_url: string;
};
export type LayerItem = Shape & { id: string; kind: string; label: string };
export type Context = {
  licence: { source_url: string }; fields: Record<string, { value: unknown; src?: string[]; from?: string }>;
  summary?: { value: string }; web?: { title: string; url: string; snippet: string }[];
};
export type DrawingFull = DrawingCard & {
  files: Record<string, string>; examples: Example[]; context: Context | null;
  standardized: any | null; std_layer: LayerItem[] | null; standardized_url: string | null;
};
export type SourceInfo = { source: string; label: string; track: string; n: number };
export type Health = { vlm: { online: boolean; reason?: string; ft_model?: string; models: string[] } };

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    const body = await r.text();
    let detail = body;
    try { detail = JSON.parse(body).detail ?? body; } catch { /* plain-text error body */ }
    throw new Error(typeof detail === "string" ? detail : `${r.status} ${body}`);
  }
  return r.json();
}
const enc = encodeURIComponent;

export const api = {
  health: () => j<Health>("/api/health"),
  drawings: () => j<{ drawings: DrawingCard[]; sources: SourceInfo[] }>("/api/drawings"),
  drawing: (id: string) => j<DrawingFull>(`/api/drawings/${enc(id)}`),
  ask: (drawing_id: string, question: string, lang?: string) =>
    j<Answer>("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ drawing_id, question, lang }) }),
  words: (id: string) => j<{ available: boolean; method?: string; words: Word[] }>(`/api/drawings/${enc(id)}/words?compute=1`),
  search: (q: string) => j<any>(`/api/search?q=${enc(q)}`),
  benchmark: () => j<any>("/api/benchmark"),
  uploads: () => j<{ drawings: DrawingCard[] }>("/api/uploads"),
  upload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return j<DrawingCard>("/api/upload", { method: "POST", body });
  },
};

export const drawingPath = (id: string) => `/d/${enc(id)}`;

const UNITS: Record<string, string> = { m2: "m²", m3: "m³", ft2: "ft²", count: "", text: "" };

export function fmtValue(v: unknown, unit?: string | null): { value: string; unit: string } {
  if (v === null || v === undefined) return { value: "—", unit: "" };
  const value = typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(2)) : Array.isArray(v) ? v.join(", ") : String(v);
  return { value, unit: unit ? UNITS[unit] ?? unit : "" };
}

export function boxOf(e: Shape): number[] | null {
  if (e.bbox) return e.bbox;
  if (!e.polygon?.length) return null;
  const xs = e.polygon.map((p) => p[0]), ys = e.polygon.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

// Bounding box around all shapes that have a position on the sheet
export function unionBox(shapes: Shape[]): number[] | null {
  const bs = shapes.map(boxOf).filter((b): b is number[] => !!b);
  if (!bs.length) return null;
  return [Math.min(...bs.map((b) => b[0])), Math.min(...bs.map((b) => b[1])), Math.max(...bs.map((b) => b[2])), Math.max(...bs.map((b) => b[3]))];
}
