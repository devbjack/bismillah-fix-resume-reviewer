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
    out = extract_requirements("job", chat=fake('{"requirements":[{"text":"Python","type":"must"}]}'))
    assert out == [{"text": "Python", "type": "must"}]


def test_clips_text_and_count():
    items = [{"text": "x" * 300, "type": "nice"} for _ in range(25)]
    out = extract_requirements("job", chat=fake(json.dumps({"requirements": items})))
    assert len(out) == 20
    assert all(len(r["text"]) == 200 for r in out)


def test_drops_bad_items():
    items = [{"text": "Go", "type": "optional"}, {"text": "  ", "type": "must"}, {"type": "must"}, {"text": "SQL", "type": "nice"}]
    out = extract_requirements("job", chat=fake(json.dumps({"requirements": items})))
    assert out == [{"text": "SQL", "type": "nice"}]


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
