import math
from typing import Any, Callable, Protocol

# Chosen by probing variants on qwen2.5:3b: a strict "only if" prompt made it answer "no" to clear matches.
SYSTEM_PROMPT = "You are an HR assistant. Answer with one word: yes or no."
USER_TEMPLATE = (
    "Resume excerpts:\n{excerpts}\n\n"
    'Question: is there evidence in these excerpts that the candidate meets the requirement "{requirement}"? '
    "Mentioning the skill, tool or degree counts as evidence.\n\nAnswer (yes or no):"
)


class Decider(Protocol):
    def p_met(self, requirement: str, evidence: list[str]) -> float: ...


class OllamaDecider:
    """P(met) from a local LLM: the model's own probability of answering 'yes' vs 'no'."""

    def __init__(self, chat: Callable[..., Any] | None = None, model: str = "qwen2.5:3b"):
        if chat is None:
            import ollama
            chat = ollama.Client().chat
        self.chat = chat
        self.model = model

    def p_met(self, requirement: str, evidence: list[str]) -> float:
        excerpts = "\n\n---\n\n".join(evidence)
        response = self.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(excerpts=excerpts, requirement=requirement)},
            ],
            options={"temperature": 0, "num_predict": 1},
            logprobs=True,
            top_logprobs=10,
        )
        p_yes = p_no = 0.0
        if response.logprobs:
            for alt in response.logprobs[0].top_logprobs:
                word = alt.token.strip().lower()
                if word == "yes":
                    p_yes += math.exp(alt.logprob)
                elif word == "no":
                    p_no += math.exp(alt.logprob)
        if p_yes + p_no > 0:
            return p_yes / (p_yes + p_no)
        # shortcut: without usable logprobs, map the plain answer to a coarse probability
        return 0.9 if response.message.content.strip().lower().startswith("yes") else 0.1
