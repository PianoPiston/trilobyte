"""Answer a question by sending the drawing + question to an OpenAI-compatible VLM endpoint (vLLM / Verda).

Returns {value, unit, evidence, confidence, conf_self, raw, tokens_in, tokens_out, latency_s}.
confidence = probability mass of the answer-value tokens (from logprobs) when available, else the
model's self-reported confidence.
"""
import asyncio, json, math, re, time
from ..images import load_image, to_data_url
from ..data import image_path_for, DATA_ROOT

SYSTEM = "You are an expert in reading construction drawings, floor plans and building documents."

PROMPT_ZS = (
    "Question: {q}\n\n"
    "Reply with ONE JSON object and nothing else:\n"
    '{{"answer": <integer for counts, number for areas/lengths/volumes, short text otherwise>, '
    '"unit": "<count|m2|m|m3|ft2|text>", '
    '"evidence": [[x0, y0, x1, y1], ...], "confidence": <0.0-1.0>}}\n'
    "evidence = bounding boxes (coordinates normalized to 0-1000) of the drawing regions that support the "
    "answer, e.g. one box per counted item or the room/label read. Answer in the unit the question asks for."
)
PROMPT_FT = "{q}"  # fine-tuned models learned the output format

_JSON = re.compile(r"\{.*\}", re.S)


def parse_output(text: str):
    t = text.strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip()
    m = _JSON.search(t)
    if m:
        s = m.group(0)
        for cand in (s, s.replace("'", '"')):
            try:
                d = json.loads(cand)
                if isinstance(d, dict):
                    return d
            except Exception:
                pass
        m2 = re.search(r'"answer"\s*:\s*("([^"]*)"|[-\d.,]+|null)', s)
        if m2:
            return {"answer": m2.group(2) if m2.group(2) is not None else m2.group(1)}
    m3 = re.search(r"-?\d+(?:[.,]\d+)?", t)
    return {"answer": m3.group(0) if m3 else (t or None), "_unparsed": True}


def answer_value_prob(lp_content):
    """Product of token probabilities over the answer value span in the generated JSON."""
    if not lp_content:
        return None
    toks = [c.token for c in lp_content]
    text = "".join(toks)
    m = re.search(r'"answer"\s*:\s*("[^"]*"|[^,}\s]+)', text)
    if not m:
        return None
    a, b = m.span(1)
    pos, lp = 0, 0.0
    for c in lp_content:
        s, e = pos, pos + len(c.token)
        if e > a and s < b:
            lp += c.logprob
        pos = e
    return math.exp(lp)


class VLMMethod:
    def __init__(self, model, base_url, api_key="EMPTY", max_pixels=2_000_000, prompt="zs",
                 max_tokens=768, extra_body=None, temperature=0.0, logprobs=True, min_pixels=0):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=600, max_retries=2)
        self.model, self.max_pixels, self.max_tokens = model, max_pixels, max_tokens
        self.prompt = PROMPT_ZS if prompt == "zs" else PROMPT_FT
        self.system = SYSTEM if prompt == "zs" else None
        self.extra_body = extra_body or {}
        self.temperature, self.logprobs, self.min_pixels = temperature, logprobs, min_pixels

    async def answer(self, q_path: str, question: str) -> dict:
        img_path = image_path_for(q_path)
        if img_path is None:
            return {"value": None, "abstain_reason": "no raster drawing (IFC) - not routed to VLM"}
        import os
        img = await asyncio.to_thread(load_image, img_path, self.max_pixels, self.min_pixels)
        url = await asyncio.to_thread(to_data_url, img)
        msgs = ([{"role": "system", "content": self.system}] if self.system else []) + [{
            "role": "user", "content": [
                {"type": "image_url", "image_url": {"url": url}},
                {"type": "text", "text": self.prompt.format(q=question)}]}]
        t0 = time.time()
        r = await self.client.chat.completions.create(
            model=self.model, messages=msgs, max_tokens=self.max_tokens, temperature=self.temperature,
            logprobs=self.logprobs or None, extra_body=self.extra_body)
        dt = time.time() - t0
        ch = r.choices[0]
        text = ch.message.content or ""
        d = parse_output(text)
        conf_lp = answer_value_prob(ch.logprobs.content) if (self.logprobs and ch.logprobs) else None
        conf_self = d.get("confidence")
        try:
            conf_self = float(conf_self) if conf_self is not None else None
        except Exception:
            conf_self = None
        ev = d.get("evidence") or []
        return {
            "value": d.get("answer"), "unit": d.get("unit"), "evidence": ev if isinstance(ev, list) else [],
            "confidence": conf_lp if conf_lp is not None else conf_self, "conf_self": conf_self,
            "conf_lp": conf_lp, "raw": text[:2000], "finish": ch.finish_reason,
            "tokens_in": r.usage.prompt_tokens if r.usage else None,
            "tokens_out": r.usage.completion_tokens if r.usage else None,
            "latency_s": dt, "img_size": list(img.size),
        }


PROMPT_GROUND = (
    "Question about this drawing: {q}\n"
    "The verified answer is: {a}\n"
    "Return ONE JSON object and nothing else: {{\"evidence\": [[x0, y0, x1, y1], ...]}} with bounding boxes "
    "(coordinates normalized to 0-1000) of every drawing element that supports this answer: one box per counted "
    "item, or the box around the room / printed label / table row that was read."
)


class FTWithEvidence:
    """Answer with the fine-tuned LoRA (cheap, accurate), then ground the answer with the *base* model on the
    same vLLM server (adapter off) to get evidence boxes. Boxes are converted to image pixel coordinates."""

    def __init__(self, ft_model, base_model, base_url, max_pixels=2_000_000, extra_body=None, ground=True):
        self.ft = VLMMethod(ft_model, base_url, max_pixels=max_pixels, prompt="ft", max_tokens=64, extra_body=extra_body)
        self.base = VLMMethod(base_model, base_url, max_pixels=max_pixels, prompt="zs", max_tokens=512,
                              extra_body=extra_body, logprobs=False)
        self.base.prompt, self.base.system = PROMPT_GROUND, SYSTEM
        self.ground = ground

    async def answer(self, q_path, question):
        r = await self.ft.answer(q_path, question)
        r["method"] = "vlm-ft"
        if not self.ground or r.get("value") is None:
            return r
        prompt = PROMPT_GROUND.replace("{a}", f"{r['value']} {r.get('unit') or ''}".strip())
        self.base.prompt = prompt
        g = await self.base.answer(q_path, question)
        w, h = r.get("img_size") or g.get("img_size") or (1000, 1000)
        boxes = []
        raw_boxes = list(g.get("evidence") or [])
        if not raw_boxes:  # Qwen native grounding format: [{"bbox_2d": [x0,y0,x1,y1], "label": ...}, ...]
            txt = re.sub(r"^```(?:json)?|```$", "", (g.get("raw") or "").strip(), flags=re.M)
            try:
                arr = json.loads(txt[txt.index("["): txt.rindex("]") + 1])
                raw_boxes = [it.get("bbox_2d") for it in arr if isinstance(it, dict) and it.get("bbox_2d")]
            except Exception:
                raw_boxes = [list(map(float, m)) for m in re.findall(r"\[\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\]", txt)]
        for b in raw_boxes:
            if isinstance(b, (list, tuple)) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b):
                boxes.append({"bbox_norm1000": b, "bbox_px": [b[0] * w / 1000, b[1] * h / 1000, b[2] * w / 1000, b[3] * h / 1000]})
        r["evidence"] = boxes
        r["evidence_method"] = "base-model grounding (adapter off)"
        r["tokens_in"] = (r.get("tokens_in") or 0) + (g.get("tokens_in") or 0)
        r["tokens_out"] = (r.get("tokens_out") or 0) + (g.get("tokens_out") or 0)
        r["latency_s"] = (r.get("latency_s") or 0) + (g.get("latency_s") or 0)
        return r


class CachedVLM:
    """Replays answers of a VLM run (results/runs/<run>.jsonl from eval.py) keyed by (path, question).
    Used when the GPU endpoint is not available: the fine-tuned model's outputs (value, logprob confidence,
    tokens, latency) for exactly these questions were produced earlier by the same checkpoint."""

    def __init__(self, run_files):
        self.cache = {}
        for fn in run_files:
            for l in open(fn):
                r = json.loads(l)
                self.cache[(r["path"], r["question"])] = r["pred"]

    async def answer(self, q_path, question):
        p = self.cache.get((q_path, question))
        if p is None:
            return {"value": None, "vlm_missing": True, "abstain_reason": "no cached VLM answer"}
        return {k: p.get(k) for k in ("value", "unit", "evidence", "confidence", "tokens_in", "tokens_out", "latency_s", "img_size")} | {"cached": True}
