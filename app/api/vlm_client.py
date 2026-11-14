"""OpenAI-compatible VLM endpoint (vLLM serving Qwen3.5-4B + the fine-tuned LoRA). Pluggable via STOA_VLM_BASE_URL.

Prompts are imported from the training/eval code so the product calls the model exactly like the evaluation did:
fine-tuned adapter = image + raw question (no system prompt, no thinking); grounding = base model, adapter off.
"""
import asyncio, json, re, time
from . import config as C


class VLMClient:
    def __init__(self):
        self._health = (0.0, None)  # (checked_at, info)
        self._client = None

    @property
    def enabled(self):
        return bool(C.VLM_BASE_URL)

    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(base_url=C.VLM_BASE_URL, api_key=C.VLM_API_KEY, timeout=C.VLM_TIMEOUT, max_retries=0)
        return self._client

    async def health(self, force=False):
        """-> {"online": bool, "models": [...], "ft_model": name|None, "base_model": name} (cached 20 s)"""
        t, info = self._health
        if not force and info is not None and time.time() - t < 20:
            return info
        if not self.enabled:
            info = {"online": False, "reason": "STOA_VLM_BASE_URL not set", "models": []}
        else:
            try:
                r = await asyncio.wait_for(self.client().models.list(), timeout=3)
                ids = [m.id for m in r.data]
                ft = C.VLM_FT_MODEL or next((i for i in ids if i != C.VLM_BASE_MODEL and "/" not in i), None)
                base = C.VLM_BASE_MODEL if C.VLM_BASE_MODEL in ids else next((i for i in ids if "/" in i), None)
                info = {"online": True, "models": ids, "ft_model": ft, "base_model": base, "endpoint": "configured"}
            except Exception as e:
                info = {"online": False, "reason": f"endpoint unreachable ({type(e).__name__})", "models": []}
        self._health = (time.time(), info)
        return info

    async def _chat(self, model, messages, max_tokens, logprobs):
        r = await self.client().chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, temperature=0, logprobs=logprobs or None,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
        return r

    async def answer(self, image_path, question, context_block=None, style="ft"):
        """fine-tuned answer (style ft) or zero-shot base answer (style zs, used with historic context)."""
        from stoa.images import load_image, to_data_url
        from stoa.methods.vlm import parse_output, answer_value_prob, SYSTEM, PROMPT_ZS
        h = await self.health()
        if not h.get("online"):
            raise RuntimeError(h.get("reason", "offline"))
        img = await asyncio.to_thread(load_image, image_path, 2_000_000)
        url = await asyncio.to_thread(to_data_url, img)
        if style == "ft" and h.get("ft_model"):
            model, text, msgs_sys = h["ft_model"], (context_block + "\n" if context_block else "") + question, None
            max_tokens = 64
        else:
            from stoa.context.method import PROMPT_ZS as HPROMPT
            model = h.get("base_model") or C.VLM_BASE_MODEL
            text = (HPROMPT.format(ctx=context_block + "\n", q=question) if context_block is not None
                    else PROMPT_ZS.format(q=question))
            msgs_sys, max_tokens = SYSTEM, 256
        msgs = ([{"role": "system", "content": msgs_sys}] if msgs_sys else []) + [{
            "role": "user", "content": [{"type": "image_url", "image_url": {"url": url}}, {"type": "text", "text": text}]}]
        t0 = time.time()
        r = await self._chat(model, msgs, max_tokens, True)
        ch = r.choices[0]
        raw = ch.message.content or ""
        d = parse_output(raw)
        conf = answer_value_prob(ch.logprobs.content) if ch.logprobs else None
        if conf is None and d.get("confidence") is not None:
            try:
                conf = float(d["confidence"])
            except Exception:
                conf = None
        return {"value": d.get("answer"), "unit": d.get("unit"), "confidence": conf, "raw": raw[:500], "model": model,
                "img_size": list(img.size), "latency_s": time.time() - t0,
                "tokens_in": r.usage.prompt_tokens if r.usage else None, "tokens_out": r.usage.completion_tokens if r.usage else None,
                "_img_url": url}

    async def ground(self, img_url, img_size, question, answer):
        """evidence boxes from the base model (adapter off) -> [[x0,y0,x1,y1] in px of the image sent]"""
        from stoa.methods.vlm import PROMPT_GROUND, SYSTEM, parse_output
        h = await self.health()
        model = h.get("base_model") or C.VLM_BASE_MODEL
        prompt = PROMPT_GROUND.replace("{a}", str(answer)).replace("{q}", question)
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": img_url}}, {"type": "text", "text": prompt}]}]
        t0 = time.time()
        r = await self._chat(model, msgs, 512, False)
        raw = r.choices[0].message.content or ""
        d = parse_output(raw)
        boxes = d.get("evidence") if isinstance(d.get("evidence"), list) else []
        if not boxes:
            txt = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M)
            try:
                arr = json.loads(txt[txt.index("["): txt.rindex("]") + 1])
                boxes = [it.get("bbox_2d") for it in arr if isinstance(it, dict) and it.get("bbox_2d")]
            except Exception:
                boxes = [list(map(float, m)) for m in re.findall(
                    r"\[\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\]", txt)]
        w, h_ = img_size
        out = []
        for b in boxes[:60]:
            if isinstance(b, (list, tuple)) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b):
                out.append([b[0] * w / 1000, b[1] * h_ / 1000, b[2] * w / 1000, b[3] * h_ / 1000])
        return out, {"latency_s": time.time() - t0, "tokens_in": r.usage.prompt_tokens if r.usage else None,
                     "tokens_out": r.usage.completion_tokens if r.usage else None}


VLM = VLMClient()
