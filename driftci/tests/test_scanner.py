from __future__ import annotations

from server.scanner import inventory, model_evidence, production_models, read_text_tree

from conftest import EXAMPLE


def test_example_fixture_maps_real_files_and_ignores_documentation():
    files = read_text_tree(EXAMPLE)
    assert len(files) == 15
    assert production_models(files) == ["gpt-4-0314", "o1-mini"]
    evidence = model_evidence(files, "gpt-4-0314")
    assert [(row["file"], row["line"]) for row in evidence] == [("src/jobs/escalation.ts", 7), ("src/lib/ai.ts", 6)]
    assert all(row["file"] != "README.md" for row in evidence)


def test_docs_never_inflate_production_models_or_call_sites():
    files = {
        "README.md": "Use gpt-4-0314 and o1-mini for this example.",
        "notes.txt": "gpt-4-0314",
        "src/one.ts": 'const model = "gpt-4-0314";',
        "src/two.py": 'MODEL = "gpt-4-0314"',
        "config.json": '{"review_model": "o1-mini"}',
    }
    assert production_models(files) == ["gpt-4-0314", "o1-mini"]
    assert len(model_evidence(files, "gpt-4-0314")) == 2


def test_unresolved_ranges_remain_inventory_without_claiming_an_exact_version():
    files = read_text_tree(EXAMPLE)
    rows = {row["name"]: row for row in inventory(files)}
    assert len(rows) == 9
    assert rows["next"]["version"] == "14.2.3"
    assert rows["next"]["exact"] is True
    assert rows["openai"]["version"] == "^4.28.0"
    assert rows["openai"]["exact"] is False
    assert rows["openai"]["health"] == "unresolved"
