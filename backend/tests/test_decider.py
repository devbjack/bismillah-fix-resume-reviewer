import math
from types import SimpleNamespace as NS

import pytest

from app.decider import OllamaDecider


def resp(content, top=None):
    """Fake ollama ChatResponse; top = {token: probability} for the first generated token."""
    logprobs = None
    if top is not None:
        logprobs = [NS(token=content, logprob=0.0,
                       top_logprobs=[NS(token=t, logprob=math.log(p)) for t, p in top.items()])]
    return NS(message=NS(content=content), logprobs=logprobs)


def fake(response, captured=None):
    def chat(**kwargs):
        if captured is not None:
            captured.update(kwargs)
        return response
    return chat


def test_probability_from_logprobs():
    d = OllamaDecider(chat=fake(resp("yes", {"yes": 0.6, "no": 0.2, "maybe": 0.2})))
    assert d.p_met("Python", ["Python dev"]) == pytest.approx(0.75)


def test_token_variants_are_summed():
    d = OllamaDecider(chat=fake(resp("No", {"No": 0.5, " no": 0.1, "Yes": 0.3, "yes": 0.1})))
    assert d.p_met("Docker", ["x"]) == pytest.approx(0.4 / 1.0)


def test_falls_back_to_answer_text_without_logprobs():
    assert OllamaDecider(chat=fake(resp("Yes."))).p_met("r", ["e"]) == 0.9
    assert OllamaDecider(chat=fake(resp("no"))).p_met("r", ["e"]) == 0.1


def test_falls_back_when_top_tokens_have_no_yes_or_no():
    assert OllamaDecider(chat=fake(resp("yes", {"Sure": 0.9}))).p_met("r", ["e"]) == 0.9


def test_sends_one_token_deterministic_request_with_logprobs():
    captured = {}
    OllamaDecider(chat=fake(resp("yes", {"yes": 1.0}), captured)).p_met("Experience with Docker", ["Built Docker images", "Used AWS"])
    assert captured["model"] == "qwen2.5:3b"
    assert captured["options"]["temperature"] == 0
    assert captured["options"]["num_predict"] == 1
    assert captured["logprobs"] is True and captured["top_logprobs"] >= 5
    prompt = captured["messages"][-1]["content"]
    assert "Experience with Docker" in prompt
    assert "Built Docker images" in prompt and "Used AWS" in prompt


@pytest.mark.slow
def test_ollama_separates_met_from_unmet():
    d = OllamaDecider()
    req = "At least 3 years of professional experience developing software in Python"
    yes = d.p_met(req, ["Senior Backend Engineer, 2019-2024. Built Python services with Django and FastAPI."])
    no = d.p_met(req, ["Graphic designer with 5 years of experience in branding and print design."])
    assert yes >= 0.5 > no
