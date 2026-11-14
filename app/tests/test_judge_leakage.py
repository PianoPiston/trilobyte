"""No-leakage checks for the candidate routes and the decision judge.

Run: ~/venvs/stoa-app/bin/python -m pytest app/tests/test_judge_leakage.py -q
  * the judge prompt for dataset drawings never contains the dataset label fields, and the gold answer appears
    in it only if a legitimate route (exact file / detector / words / model) produced that same value
  * the dataset label (reference) is looked up only AFTER the decision
  * answer-cache records carry model output fields only
"""
import asyncio, json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ["STOA_OCR_ON_ASK"] = "0"
from app.api import config as C, catalog as CAT, engine as E  # noqa: E402
from stoa import decide as D  # noqa: E402

DRAWINGS = ["cubicasa5k~high_quality-3650", "cubicasa5k~high_quality_architectural-14814", "swiss_dwellings~site3634_bldg5596_floor24203"]


def _examples():
    for did in DRAWINGS:
        d = CAT.describe(did)
        if d is None:
            continue
        for ex in CAT.example_questions(d, limit=8):
            if ex.get("answer") is not None:
                yield did, ex


def test_judge_prompt_has_no_gold():
    n = 0
    for did, ex in _examples():
        r = asyncio.run(E.ask(did, ex["question"], use_vlm=False, use_judge=False))
        cands = [{k: c[k] for k in ("value", "unit", "scope", "source", "confidence", "reason")} for c in r["ranked_candidates"]]
        msgs = D.judge_prompt(ex["question"], [{**c, "id": f"c{i + 1}"} for i, c in enumerate(cands)])
        text = json.dumps(msgs, ensure_ascii=False)
        D.assert_no_leak(text, ex, legit_values=[c["value"] for c in cands])
        for c in r["ranked_candidates"]:
            assert not set(c) & {"reference", "accept", "gold", "match"}, c.keys()
        n += 1
    assert n > 0


def test_reference_only_after_decision(monkeypatch):
    seen = {"decided": False, "ref_before": False}
    orig_decide, orig_ref = D.decide, E.reference_for

    async def spy_decide(*a, **k):
        seen["decided"] = True
        return await orig_decide(*a, **k)

    def spy_ref(d, q):
        if not seen["decided"]:
            seen["ref_before"] = True
        return orig_ref(d, q)

    monkeypatch.setattr(D, "decide", spy_decide)
    monkeypatch.setattr(E, "reference_for", spy_ref)
    did, ex = next(_examples())
    r = asyncio.run(E.ask(did, ex["question"], use_vlm=False, use_judge=False))
    assert seen["decided"] and not seen["ref_before"]
    assert "reference" in r  # the UI still gets the label, after the decision


def test_judge_rejects_invented_ids():
    assert D.parse_judge('{"ranking": ["c9"], "unsure": false}', ["c1", "c2"]) is None
    assert D.parse_judge('not json', ["c1"]) is None
    assert D.parse_judge('{"ranking": ["c2"], "unsure": true}', ["c1", "c2"]) == (["c2", "c1"], True)


def test_scope_rule_room_never_total():
    cands = [{"value": 12.5, "unit": "m2", "scope": "room:kitchen", "source": "text", "confidence": 0.9},
             {"value": 68.5, "unit": "m2", "scope": "total", "source": "text", "confidence": 0.8}]
    out = asyncio.run(D.decide("What is the total area of the apartment?", "total", cands, chat=None))
    assert [c["value"] for c in out["ranked"]] == [68.5]
    assert out["dropped"][0]["value"] == 12.5


def test_cache_records_are_model_output_only():
    allowed = {"q_path", "question", "value", "unit", "confidence", "method", "origin", "evidence", "run", "at"}
    for fn in (C.ANSWER_CACHE, C.LIVE_CACHE):
        if os.path.exists(fn):
            for line in open(fn, encoding="utf-8"):
                assert set(json.loads(line)) <= allowed
