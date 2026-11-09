import json
from types import SimpleNamespace

import pytest

from app.req_extract import SCHEMA, RequirementsUnavailable, extract_requirements


def fake(content, captured=None):
    def chat(**kwargs):
        if captured is not None:
            captured.update(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content=content))
    return chat


def test_parses_schema_output():
    out = extract_requirements("job", chat=fake('{"must_have":["Python"],"nice_to_have":["Docker"]}'))
    assert out == [{"text": "Python", "type": "must"}, {"text": "Docker", "type": "nice"}]


def test_schema_requires_both_lists():
    assert set(SCHEMA["required"]) == {"must_have", "nice_to_have"}


def test_clips_text_and_count():
    out = extract_requirements("job", chat=fake(json.dumps({"must_have": ["x" * 300] * 15, "nice_to_have": ["y" * 300] * 10})))
    assert len(out) == 20
    assert all(len(r["text"]) == 200 for r in out)
    assert [r["type"] for r in out].count("nice") == 5


def test_drops_bad_items():
    out = extract_requirements("job", chat=fake(json.dumps({"must_have": ["  ", 7, None], "nice_to_have": ["SQL"]})))
    assert out == [{"text": "SQL", "type": "nice"}]


def test_missing_list_is_empty():
    assert extract_requirements("job", chat=fake('{"must_have":["Go"]}')) == [{"text": "Go", "type": "must"}]


def test_passes_schema_and_temperature_zero():
    captured = {}
    extract_requirements("job text here", chat=fake('{"requirements":[]}', captured))
    assert captured["format"] == SCHEMA
    assert captured["options"]["temperature"] == 0
    assert captured["model"] == "qwen2.5:3b"
    assert "job text here" in captured["messages"][-1]["content"]


def test_connection_error_raises_unavailable():
    def chat(**kwargs):
        raise ConnectionError("refused")
    with pytest.raises(RequirementsUnavailable):
        extract_requirements("job", chat=chat)


def test_invalid_json_returns_empty():
    assert extract_requirements("x", chat=fake("not json")) == []


@pytest.mark.slow
def test_real_ollama_extracts_must_and_nice_from_sample_job():
    from pathlib import Path

    from app.pdf_text import extract_text
    job = (Path(__file__).resolve().parents[2] / "samples" / "job.pdf").read_bytes()
    reqs = extract_requirements(extract_text(job))
    types = [r["type"] for r in reqs]
    assert types.count("must") == 4
    assert types.count("nice") == 4
    assert any("docker" in r["text"].lower() and r["type"] == "nice" for r in reqs)
