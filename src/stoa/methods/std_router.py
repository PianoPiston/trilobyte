"""Router v2: standardized files first, model evidence second, "needs check" otherwise.

  swiss_dwellings / ifc_models -> exact standardized file (DXF / IFC) -> deterministic answer.
                                  Ambiguous cases (flags) -> needs check. Unsupported intents -> fine-tuned VLM.
  cubicasa5k (raster)          -> model standardized file (detector boxes) + fine-tuned VLM answer;
                                  answered only when the calibrated policy accepts (agreement / clean detections /
                                  high VLM confidence), else needs check with both candidates and the evidence boxes.
  everything else              -> fine-tuned VLM, answered only above the calibrated confidence threshold.

The policy (thresholds per intent) is calibrated on VAL only (scripts/calibrate_router.py). With policy=None
the router answers everything with its best candidate and records all signals (used to collect VAL signals).
Answers with value None carry `needs_check: True`, `candidates` and `evidence`.
"""
import asyncio, json, os
from ..answer import answer_std, parse_intent, query
from ..data import DATA_ROOT

DET_KEYS = {("count_windows", None): "windows", ("count_doors", None): "doors", ("count_symbol", "toilet"): "toilet",
            ("count_symbol", "sink"): "sink", ("count_symbol", "showers_baths"): "showers_baths", ("count_saunas", None): "saunas"}
DET_CLASSES = {"windows": ["window"], "doors": ["door"], "toilet": ["toilet"], "sink": ["sink"],
               "showers_baths": ["shower", "bathtub"], "saunas": ["sauna_stove"]}
ROOM_DET = {f"count_room_type:{t}": [f"room_{t}"] for t in ("bedroom", "kitchen", "bath", "wc", "balcony")}


def intent_key(intent):
    k = intent["kind"]
    return DET_KEYS.get((k, intent.get("symbol"))) or (k + (":" + intent["type"] if intent.get("type") else "")
                                                       + (":" + intent["symbol"] if intent.get("symbol") else ""))


class StdRouter:
    def __init__(self, vlm=None, det_cache=None, det_policy=None, policy=None, auto_threshold=0.95):
        """vlm: object with async answer(path, q) (fine-tuned VLM, e.g. FTWithEvidence or VLMMethod prompt=ft)
        det_cache: JSONL from scripts/run_detector.py; policy: dict or JSON path (calibrate_router.py output)"""
        self.vlm = vlm
        self.dets = {}
        if det_cache:
            for l in open(det_cache):
                r = json.loads(l)
                self.dets[r["path"]] = r
        from ..convert.raster_model import load_policy
        self.det_policy = load_policy(det_policy)
        self.room_det = "room_bedroom" in self.det_policy.get("thresholds", {})
        if isinstance(policy, str):
            policy = json.loads(policy) if policy.strip().startswith("{") else json.load(open(policy))
        self.policy = policy
        self.auto = auto_threshold

    def _vlm_ok(self, src, key, conf):
        if self.policy is None:
            return True
        t = self.policy.get("vlm_threshold", {}).get(f"{src}|{key}", self.policy.get("vlm_threshold", {}).get(src, 1.01))
        return conf is not None and conf >= t

    async def _vlm(self, q_path, question):
        if self.vlm is None:
            return None
        try:
            return await self.vlm.answer(q_path, question)
        except Exception as e:
            return {"value": None, "error": repr(e)[:200]}

    async def answer(self, q_path, question):
        src = q_path.split("/")[1]
        if src in ("swiss_dwellings", "ifc_models"):
            r = await asyncio.to_thread(answer_std, q_path, question)
            if r.get("value") is not None:
                r.setdefault("tokens_in", 0); r.setdefault("tokens_out", 0)
                if r["confidence"] >= self.auto or self.policy is None:
                    return r
                return {"value": None, "needs_check": True, "candidates": [{"value": r["value"], "source": r["method"],
                        "confidence": r["confidence"], "flags": r.get("flags")}], "evidence": r["evidence"],
                        "method": r["method"] + ":needs_check", "confidence": r["confidence"], "flags": r.get("flags"),
                        "suggested_value": r["value"], "suggested_by": "exact-file (ambiguous rule)",
                        "tokens_in": 0, "tokens_out": 0, "std_value": r["value"]}
            # intent not answerable from the exact file -> VLM
        if src == "cubicasa5k" and q_path in self.dets:
            return await self._cubicasa(q_path, question)
        v = await self._vlm(q_path, question)
        if v is None:
            return {"value": None, "needs_check": True, "method": "none", "abstain_reason": "no route"}
        key = intent_key(parse_intent(question))
        v["method"] = "vlm-ft"
        v["intent_key"] = key
        if v.get("value") is not None and not self._vlm_ok(src, key, v.get("confidence")):
            v["candidates"] = [{"value": v["value"], "source": "vlm-ft", "confidence": v.get("confidence")}]
            v["vlm_value"] = v["value"]; v["suggested_value"] = v["value"]; v["suggested_by"] = "vlm"
            v["value"] = None; v["needs_check"] = True; v["method"] = "vlm-ft:needs_check"
        return v

    async def _cubicasa(self, q_path, question):
        from ..convert.raster_model import from_detections
        intent = parse_intent(question)
        key = intent_key(intent)
        d = self.dets[q_path]
        doc = from_detections(q_path, d["size"], d["dets"], self.det_policy)
        v = await self._vlm(q_path, question)
        vval, vconf = (v or {}).get("value"), (v or {}).get("confidence")
        try:
            vval_i = int(round(float(vval))) if vval is not None else None
        except (TypeError, ValueError):
            vval_i = None
        base = {"tokens_in": (v or {}).get("tokens_in", 0), "tokens_out": (v or {}).get("tokens_out", 0),
                "latency_s": (v or {}).get("latency_s"), "vlm_value": vval_i, "vlm_conf": vconf, "intent_key": key,
                "drawing_id": doc["drawing_id"], "ground_truth_eligible": False}
        det_classes = DET_CLASSES.get(key) or (ROOM_DET.get(key) if self.room_det else None)
        if det_classes:
            q = query(doc, intent)
            dval = q["value"] if q else None
            unc = sum(doc["quality"]["uncertain_detections"].get(c, 0) for c in det_classes)
            ev = q["evidence"] if q else []
            from ..convert.raster_model import tta_counts
            views = tta_counts(d.get("tta"), self.det_policy)
            vcounts = [sum(v.get(c, 0) for c in det_classes) for v in views]
            tta_stable = bool(views) and dval is not None and all(x == dval for x in vcounts)
            sig = {"det_value": dval, "det_uncertain": unc, "agree": dval is not None and dval == vval_i,
                   "tta_counts": vcounts, "tta_stable": tta_stable}
            acc = self._accept_det(key, sig, vconf)
            if self.policy is None or acc:
                val = dval if (self.policy is None or acc in ("det", "agree")) else vval_i
                return {**base, **sig, "value": val, "unit": "count", "evidence": ev, "accepted_by": acc,
                        "confidence": 0.99 if acc else (vconf or 0), "method": f"det+vlm:{acc or 'collect'}"}
            sug_src = (self.policy or {}).get("suggest", {}).get(key, "detector")
            return {**base, **sig, "value": None, "needs_check": True, "evidence": ev, "confidence": vconf,
                    "suggested_value": dval if sug_src == "detector" else vval_i, "suggested_by": sug_src,
                    "candidates": [{"value": dval, "source": "detector", "uncertain_boxes": unc},
                                   {"value": vval_i, "source": "vlm-ft", "confidence": vconf}],
                    "method": "det+vlm:needs_check"}
        # room-type / floor counts: VLM only (no detector class)
        ev = (v or {}).get("evidence", [])
        if vval_i is not None and self._vlm_ok("cubicasa5k", key, vconf):
            return {**base, "value": vval_i, "unit": "count", "evidence": ev, "confidence": vconf, "method": "vlm-ft"}
        return {**base, "value": None, "needs_check": True, "evidence": ev, "confidence": vconf, "suggested_value": vval_i,
                "suggested_by": "vlm", "candidates": [{"value": vval_i, "source": "vlm-ft", "confidence": vconf}],
                "method": "vlm-ft:needs_check"}

    def _accept_det(self, key, sig, vconf):
        if self.policy is None:
            return None
        rules = self.policy.get("det_rules", {}).get(key, [])
        for r in rules:
            if r == "agree" and sig["agree"]:
                return "agree"
            if r == "agree_clean" and sig["agree"] and sig["det_uncertain"] == 0:
                return "agree"
            if r == "det_clean" and sig["det_uncertain"] == 0 and sig["det_value"] is not None:
                return "det"
            if r == "tta" and sig.get("tta_stable"):
                return "det"
            if r == "agree_tta" and sig["agree"] and sig.get("tta_stable"):
                return "agree"
            if r.startswith("vlm>=") and vconf is not None and vconf >= float(r[5:]):
                return "vlm"
        return None
