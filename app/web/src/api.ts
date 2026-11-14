export type Evidence = {
  id: string; label: string; kind?: string; element_id?: string | null; ifc_global_id?: string;
  polygon?: number[][]; bbox?: number[]; approximate?: boolean; off_sheet?: boolean;
};
export type Candidate = {
  rank: number; id: string; value: unknown; unit?: string | null; scope?: string | null; source: string; source_label?: string;
  method: string; confidence: number | null; evidence: Evidence[]; reason?: string | null; agree_with: string[]; flags: string[];
};
export type Word = { text: string; bbox: number[]; conf?: number | null };
export type Source = { label: string; url?: string | null };
export type Answer = {
  drawing_id: string; question: string; lang: string; answer: unknown; unit?: string | null;
  method: "dxf-exact" | "ifc-exact" | "detector" | "vlm" | "cache" | "context" | "text" | "none";
  method_label: string; method_detail?: string; cached_method?: string | null;
  confidence: number | null; needs_check: boolean; needs_check_reasons: string[];
  evidence: Evidence[]; sources: Source[]; note?: string | null; cost_eur: number; latency_ms: number;
  route_trace: { route: string; result: string }[]; ground_truth_eligible: boolean;
  suggested_answer?: unknown;
  ranked_candidates?: Candidate[]; decider?: string; question_scope?: string | null;
  judge?: { latency_s?: number; tokens_in?: number; tokens_out?: number; unsure?: boolean; error?: string } | null;
  reference?: { answer: unknown; unit?: string | null; source: string; match: boolean | null };
};
export type Example = { question: string; answer: unknown; unit?: string | null; type?: string; lang: string; origin?: string };
export type DrawingCard = {
  id: string; source: string; source_label: string; title: string; subtitle: string; formats: string[];
  split: string | null; seen_in_training: boolean | null; track: "modern" | "historic";
  licence: string | null; credit: string | null; source_url: string | null; has_context: boolean; has_std: boolean;
  image_size: [number, number]; n_questions?: number; teaser?: string[]; thumb_url: string; image_url: string;
};
export type LayerItem = { id: string; kind: string; label: string; polygon?: number[][]; bbox?: number[]; type?: string | null };
export type CtxField = { value: unknown; src?: string[]; from?: string };
export type Context = {
  source: string; stem: string; licence: { licence: string; credit: string; source_url: string };
  fields: Record<string, CtxField>; summary?: { value: string }; web?: { title: string; url: string; snippet: string; relevance?: string }[];
  sources?: string[]; trust?: string;
};
export type DrawingFull = DrawingCard & {
  q_path: string; files: Record<string, string>; examples: Example[]; context: Context | null;
  standardized: any | null; std_layer: LayerItem[] | null; standardized_url: string | null;
};
export type Health = { ok: boolean; vlm: { online: boolean; reason?: string; ft_model?: string; base_model?: string; models: string[] };
  drawings: number; answer_cache: number; conf_threshold: number };

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
export const api = {
  health: () => j<Health>("/api/health"),
  drawings: () => j<{ drawings: DrawingCard[]; sources: { source: string; label: string; track: string; n: number }[] }>("/api/drawings"),
  drawing: (id: string) => j<DrawingFull>(`/api/drawings/${encodeURIComponent(id)}`),
  ask: (drawing_id: string, question: string, lang?: string) =>
    j<Answer>("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ drawing_id, question, lang }) }),
  words: (id: string, compute = true) =>
    j<{ available: boolean; method?: string; engine?: string; words: Word[] }>(`/api/drawings/${encodeURIComponent(id)}/words?compute=${compute ? 1 : 0}`),
  search: (q: string) => j<any>(`/api/search?q=${encodeURIComponent(q)}`),
  benchmark: () => j<any>("/api/benchmark"),
  uploads: () => j<{ drawings: (DrawingCard & { detector?: any; uploaded_at?: string })[] }>("/api/uploads"),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return j<DrawingCard & { detector?: { ok: boolean; seconds?: number; counts?: Record<string, number>; error?: string } }>("/api/upload", { method: "POST", body: fd });
  },
};

export const SOURCE_COLORS: Record<string, string> = {
  cubicasa5k: "#2a78d6", swiss_dwellings: "#c0392b", ifc_models: "#1b8a5a", opening_design: "#6250d6",
  habs: "#8a6d3b", finna: "#8a6d3b", europeana: "#8a6d3b", wikimedia: "#8a6d3b",
};

export function fmtValue(v: unknown, unit?: string | null): { value: string; unit: string } {
  if (v === null || v === undefined) return { value: "—", unit: "" };
  let s: string;
  if (typeof v === "number") s = Number.isInteger(v) ? String(v) : v.toFixed(2);
  else if (Array.isArray(v)) s = v.join(", ");
  else s = String(v);
  const u = unit === "m2" ? "m²" : unit === "m3" ? "m³" : unit === "ft2" ? "ft²" : unit === "count" || unit === "text" || !unit ? "" : unit;
  return { value: s, unit: u };
}
export const fmtEur = (e: number) => (e === 0 ? "€0" : e < 0.0001 ? `€${(e * 1000).toFixed(4)} / 1k → €${e.toExponential(1)}` : `€${e.toFixed(5)}`);
