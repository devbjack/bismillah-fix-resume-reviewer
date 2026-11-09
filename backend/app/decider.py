import math
from typing import Any, Callable, Protocol

SYSTEM_PROMPT = (
    "You check one job requirement against excerpts from a candidate's resume. "
    "Answer 'yes' only if the excerpts show the candidate meets the requirement; otherwise answer 'no'. "
    "Judge the exact skill, tool, degree or amount of experience asked for: different experience that "
    "merely sounds similar (for example, years in another profession) does not count. "
    "Answer with one word: yes or no."
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
                {"role": "user", "content": f"Requirement: {requirement}\n\nResume excerpts:\n{excerpts}\n\n"
                                            "Does the candidate meet the requirement? Answer yes or no."},
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
