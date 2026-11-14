"""Router: deterministic routes first (exact, cheap, polygon evidence), VLM fallback for the rest.
Each answer carries `method` so the per-route accuracy can be reported."""


class Router:
    def __init__(self, deterministic, fallback):
        self.det, self.fb = deterministic, fallback

    async def answer(self, q_path, question):
        for m in self.det:
            try:
                r = await m.answer(q_path, question)
            except Exception as e:  # never let a parser crash an answer
                r = {"value": None, "error_det": repr(e)[:200]}
            if r.get("value") is not None:
                r.setdefault("tokens_in", 0); r.setdefault("tokens_out", 0)
                return r
        if self.fb is None:
            return {"value": None, "abstain_reason": "no route"}
        r = await self.fb.answer(q_path, question)
        r.setdefault("method", "vlm")
        return r
