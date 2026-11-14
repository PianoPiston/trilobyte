"""Final decision maker: rank answer candidates from all routes, optionally with a text-only LLM judge.

Candidate = {id, value, unit, scope, source, source_label, confidence, evidence, reason, flags}
  source in: exact (DXF/IFC standardized file), text (printed words: PDF vector text or OCR), detector,
             vlm (live fine-tuned model), cache (earlier model output), context (archive record)

Hard priors (applied before and after the judge, never overridden):
  * a candidate whose scope does not match the question's scope is dropped (room area never answers a total)
  * exact CAD/IFC beats everything (the judge is not even called when a clean exact candidate exists)
  * printed text in the matching room beats geometric / model estimates for areas
The judge (Qwen3.5-4B base on the live vLLM endpoint) may only REORDER existing candidate ids or say "unsure".
Its output is validated: unknown ids, invented numbers or parse errors -> deterministic ranking.

NO LEAKAGE: candidates are built only from source files (DXF/IFC), detector output, words of the drawing and
model outputs. Dataset labels (questions.jsonl answers, catalog example answers, reference/accept fields, eval
correctness fields, CubiCasa SVG annotations) never enter a candidate or the judge prompt.
`assert_no_leak` checks a prompt against the gold record (used in tests and, cheaply, at runtime for dataset
drawings when STOA_LEAK_GUARD=1).
"""
import json, os, re, time

SOURCE_LABEL = {"exact": "Exact (CAD/IFC file)", "text": "Printed text on the drawing", "detector": "Symbol detector",
                "vlm": "AI model (fine-tuned VLM)", "cache": "Cached AI answer", "context": "Archive record"}
# deterministic prior order (lower = stronger). Per-scope overrides come from the VAL-calibrated policy file.
TIER = {"exact": 0, "context": 0, "text": 1, "detector": 2, "vlm": 3, "cache": 4}
FORBIDDEN_KEYS = ("reference", "accept", "gold", "answer_gold", "correct", "is_correct", "match")
POLICY_FILE = os.environ.get("STOA_DECIDE_POLICY", os.path.join(os.path.dirname(__file__), "..", "..", "results", "decide_policy.json"))


def load_policy():
    try:
        return json.load(open(POLICY_FILE))
    except Exception:
        return {}


def norm_value(v):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if isinstance(v, list):
        return tuple(norm_value(x) for x in v)
    try:
        return round(float(str(v).replace(",", ".")), 2)
    except ValueError:
        return re.sub(r"\s+", " ", str(v).strip().lower())


def scope_ok(q_scope, c_scope):
    """hard scope rule: totals only from totals, a room only from that room, counts only from the same count"""
    if not q_scope or not c_scope or c_scope == "any":
        return True
    if q_scope == "total":
        return c_scope == "total"
    if c_scope == "total":
        return False
    if q_scope.startswith("room:") or q_scope.startswith("rooms_sum:"):
        return c_scope == q_scope
    return True


AREA_UNITS = {"m2", "m²", "ft2", "sqm", "sq m"}


def unit_ok(expected, unit):
    """hard rule: a count never answers an area/scale question and vice versa"""
    if not expected or unit is None:
        return True
    u = str(unit).lower()
    if expected == "area":
        return u in AREA_UNITS
    if expected == "count":
        return u in ("count", "")
    if expected == "text":
        return u not in ("count",) and u not in AREA_UNITS
    return True


def clean_candidate(c):
    """whitelist the fields a candidate may carry (no dataset label can ride along)"""
    keep = ("id", "value", "unit", "scope", "source", "source_label", "confidence", "evidence", "reason", "flags", "rule",
            "method", "method_detail", "sources", "note", "cached_method", "model_raw")
    out = {k: c[k] for k in keep if k in c}
    out["source_label"] = out.get("source_label") or SOURCE_LABEL.get(c.get("source"), c.get("source"))
    out["flags"] = list(out.get("flags") or [])
    return out


def support(cands):
    """number of OTHER sources that agree on each candidate's value"""
    for c in cands:
        nv = norm_value(c["value"])
        c["agree_with"] = sorted({o["source"] for o in cands if o is not c and o["source"] != c["source"] and norm_value(o["value"]) == nv})
    return cands


def scope_key_for(question, q_scope):
    """policy key: the question kind for counts (count:count_symbol:toilet, count:count_room_type:bedroom, ...),
    the scope otherwise (total, room:<type>, room:label, scale ...)"""
    if q_scope and str(q_scope).startswith("room:label:"):
        return "room:label"
    if q_scope is None or str(q_scope).startswith("count:") or str(q_scope).startswith("other:"):
        from .answer import parse_intent
        i = parse_intent(question)
        return "count:" + i["kind"] + (":" + i["type"] if i.get("type") else "") + (":" + i["symbol"] if i.get("symbol") else "")
    return str(q_scope)


def rank_deterministic(cands, scope_key=None, policy=None):
    """exact first; then values supported by more independent sources (majority); then the VAL-calibrated source
    order for this question kind (default TIER); then confidence"""
    policy = policy if policy is not None else load_policy()
    order = (policy.get("source_order") or {}).get(scope_key or "", None)
    tier = {s: i for i, s in enumerate(order)} if order else TIER

    def key(c):
        conf = c.get("confidence") or 0.0
        return (0 if c["source"] == "exact" else 1, -len(c.get("agree_with", [])), tier.get(c["source"], 9), -conf)
    return sorted(cands, key=key)


def final_confidence(top, cands, policy=None, scope_key=None):
    """confidence of the chosen answer: the best confidence among the sources that give this value, raised to the
    VAL-measured precision when an agreement pattern was >= 97% correct on VAL, capped when a source that is
    reliable for this question kind (VAL) disagrees"""
    policy = policy if policy is not None else load_policy()
    c = top.get("confidence") or 0.0
    if top["source"] == "exact":
        return c
    nv = norm_value(top["value"])
    same = {top["source"]} | {o["source"] for o in cands if o is not top and norm_value(o["value"]) == nv}
    c = max([c] + [o.get("confidence") or 0.0 for o in cands if o is not top and norm_value(o["value"]) == nv])
    rules = (policy.get("agreement_conf") or {}).get(scope_key or "", {})
    for combo, conf in rules.items():
        if set(combo.split("+")) <= same:
            c = max(c, conf)
    agreed = any(set(combo.split("+")) <= same for combo in rules)
    cap = (policy.get("conf_cap") or {}).get(scope_key or "")
    if cap is not None and not agreed:
        c = min(c, cap)  # no single source is reliable for this kind on VAL -> needs check unless an agreement rule fired
    veto = set((policy.get("veto_sources") or {}).get(scope_key or "", ["exact", "detector", "vlm", "text"]))
    if any(o["source"] in veto and o["source"] not in same and (o.get("confidence") or 0) >= 0.7 for o in cands if o is not top):
        c = min(c, 0.6)
    return round(c, 4)


# ------------------------------------------------------------------------------------------------ LLM judge
JUDGE_SYSTEM = ("You check answers about a construction drawing. You never compute or invent numbers: you only rank the "
                "candidate answers you are given, by how well their evidence and scope fit the question.")


def _fmt_val(v, u):
    if isinstance(v, list):
        return "[" + ", ".join(str(x) for x in v) + "]" + (f" {u}" if u and u not in ("count", "text") else "")
    return f"{v}" + (f" {u}" if u and u not in ("count", "text") else "")


def judge_prompt(question, cands):
    """text-only prompt (short). Contains ONLY the question and the candidates' own fields."""
    lines = []
    for c in cands:
        conf = c.get("confidence")
        lines.append(f"{c['id']}: value={_fmt_val(c['value'], c.get('unit'))} | scope={c.get('scope') or '-'} | source={c['source']}"
                     f" | conf={'n/a' if conf is None else round(conf, 2)} | why={str(c.get('reason') or '')[:140]}")
    user = (f"Question: {question.strip()[:300]}\n\nCandidates:\n" + "\n".join(lines) +
            "\n\nRules: exact CAD/IFC data beats everything; printed text in the matching room beats detector or AI estimates; "
            "a candidate whose scope does not match the question (e.g. one room vs. the whole apartment) is wrong; "
            "agreement between independent sources is strong evidence.\n"
            'Reply with JSON only: {"ranking": [ids best first], "unsure": true|false}')
    return [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]


def parse_judge(raw, ids):
    """-> (ranking, unsure) or None. Only existing ids; no numbers outside ids are accepted as answers."""
    if not raw:
        return None
    txt = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        d = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
    except Exception:
        return None
    rk = d.get("ranking")
    if not isinstance(rk, list) or not rk:
        return None
    seen, out = set(), []
    for r in rk:
        r = str(r).strip()
        if r not in ids:
            return None  # invented id / value -> reject the whole judgement
        if r not in seen:
            seen.add(r); out.append(r)
    out += [i for i in ids if i not in seen]
    return out, bool(d.get("unsure"))


async def decide(question, q_scope, cands, chat=None, use_judge=True, scope_key=None, timeout=8.0, policy=None, expected_unit=None):
    """-> {"ranked": [...], "decider": "exact"|"deterministic"|"judge"|"judge-fallback", "judge": {...}, "dropped": [...]}
    chat: async callable(messages, max_tokens) -> (text, usage dict) for the judge, or None"""
    policy = policy if policy is not None else load_policy()
    cands = [clean_candidate(c) for c in cands if c.get("value") is not None]
    for i, c in enumerate(cands):
        c["id"] = f"c{i + 1}"
    kept = [c for c in cands if scope_ok(q_scope, c.get("scope")) and unit_ok(expected_unit, c.get("unit"))]
    dropped = [c for c in cands if c not in kept]
    for c in dropped:
        why = (f"scope {c.get('scope')} does not match the question ({q_scope})" if not scope_ok(q_scope, c.get("scope"))
               else f"unit {c.get('unit')} does not fit the question ({expected_unit})")
        c["reason"] = f"dropped: {why}. " + str(c.get("reason") or "")
    support(kept)
    det = rank_deterministic(kept, scope_key, policy)
    out = {"ranked": det, "decider": "deterministic", "judge": None, "dropped": dropped}
    if not det:
        return out
    if det[0]["source"] == "exact" and (det[0].get("confidence") or 0) >= 0.95 and not det[0].get("flags"):
        out["decider"] = "exact"
        return out
    distinct = {norm_value(c["value"]) for c in det}
    # VAL decides: kinds where the judge was not better than the deterministic ranking stay deterministic.
    # judge_scopes=None (calibration runs) lets the judge rank every kind.
    judge_kinds = policy.get("judge_scopes", "default")
    if judge_kinds is None:
        allowed = True
    else:
        allowed = (scope_key or "") not in set(policy.get("deterministic_scopes", [])) or (scope_key or "") in set(judge_kinds or [])
    if not (use_judge and chat and len(distinct) >= 2 and allowed):
        return out
    msgs = judge_prompt(question, det)
    t0 = time.time()
    try:
        import asyncio
        raw, usage = await asyncio.wait_for(chat(msgs, 120), timeout=timeout)
    except Exception as e:
        out["decider"] = "judge-fallback"
        out["judge"] = {"error": f"{type(e).__name__}", "latency_s": round(time.time() - t0, 2)}
        return out
    ids = [c["id"] for c in det]
    pj = parse_judge(raw, ids)
    info = {"raw": (raw or "")[:300], "latency_s": round(time.time() - t0, 2), **(usage or {})}
    if pj is None:
        out["decider"] = "judge-fallback"
        info["error"] = "unparseable or invalid ids"
        out["judge"] = info
        return out
    ranking, unsure = pj
    by = {c["id"]: c for c in det}
    ranked = [by[i] for i in ranking]
    # hard priors survive the judge: exact first, then printed text in the matching room/total (areas), then the rest;
    # mismatched scope was already dropped
    def prior(c):
        if c["source"] == "exact":
            return 0
        if c["source"] == "text" and str(c.get("scope") or "").startswith(("room:", "total", "rooms_sum:")) and \
                str(c.get("rule") or "") in ("text:room_area", "text:room_area_list", "text:total"):
            return 1
        return 2
    ranked = sorted(ranked, key=prior)
    info["unsure"] = unsure
    out.update(ranked=ranked, decider="judge", judge=info)
    return out


def assert_no_leak(prompt_text, gold_record, legit_values=()):
    """raise AssertionError if a dataset label (or its field names) shows up in a judge prompt.
    gold_record: the questions.jsonl / catalog example record for this question. A gold value may appear only when
    a legitimate candidate route produced the same value (legit_values)."""
    txt = json.dumps(prompt_text, ensure_ascii=False) if not isinstance(prompt_text, str) else prompt_text
    low = txt.lower()
    for k in ("\"reference\"", "\"accept\"", "\"gold\"", "reference:", "accept:", "gold:", "dataset label"):
        assert k not in low, f"label field name {k!r} in judge prompt"
    if gold_record is None:
        return True
    golds = [gold_record.get("answer")] + list(gold_record.get("accept") or [])
    legit = {str(norm_value(v)) for v in legit_values}
    for g in golds:
        if g is None or str(norm_value(g)) in legit:
            continue
        gs = str(g)
        if len(gs) >= 3 or not gs.replace(".", "").isdigit():  # short numbers collide with ids/confidences; checked via values
            assert gs.lower() not in low, f"gold answer {gs!r} appears in the judge prompt but no candidate produced it"
    return True
