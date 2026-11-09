import json
from typing import Any, Callable

MAX_REQUIREMENTS = 20
MAX_TEXT = 200

# Two required lists: with one list of typed items, small models stop after the "required" section.
SCHEMA = {
    "type": "object",
    "properties": {
        "must_have": {"type": "array", "items": {"type": "string"}},
        "nice_to_have": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["must_have", "nice_to_have"],
}

SYSTEM_PROMPT = (
    "You read a job posting and list every candidate requirement in it. "
    "Write each as one short statement about a single skill, tool, degree or amount of experience. "
    "Put required items (for example under 'Requirements' or 'Qualifications') in must_have. "
    "Put items under headings such as 'Nice to have', 'Preferred', 'Bonus' or 'A plus' in nice_to_have. "
    "Ignore the company description, benefits and salary."
)


class RequirementsUnavailable(Exception):
    pass


def extract_requirements(job_text: str, chat: Callable[..., Any] | None = None,
                         model: str = "qwen2.5:3b") -> list[dict]:
    if chat is None:
        import ollama
        chat = ollama.Client().chat
    try:
        response = chat(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": job_text}],
            format=SCHEMA,
            options={"temperature": 0},
        )
    except Exception as e:
        raise RequirementsUnavailable(str(e)) from e
    try:
        data = json.loads(response.message.content)
    except ValueError:
        return []
    out = []
    for key, kind in (("must_have", "must"), ("nice_to_have", "nice")):
        items = data.get(key) if isinstance(data, dict) else None
        for item in items if isinstance(items, list) else []:
            text = item.strip()[:MAX_TEXT] if isinstance(item, str) else ""
            if text:
                out.append({"text": text, "type": kind})
    return out[:MAX_REQUIREMENTS]
