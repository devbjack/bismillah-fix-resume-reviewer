import json
from typing import Any, Callable

MAX_REQUIREMENTS = 20
MAX_TEXT = 200

SCHEMA = {
    "type": "object",
    "properties": {
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "type": {"type": "string", "enum": ["must", "nice"]},
                },
                "required": ["text", "type"],
            },
        }
    },
    "required": ["requirements"],
}

SYSTEM_PROMPT = (
    "Extract the job requirements as short, single-skill statements. "
    "Mark as 'must' anything stated as required; mark 'nice' anything stated "
    "as preferred, a plus, or nice to have."
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
        items = json.loads(response.message.content)["requirements"]
    except (ValueError, KeyError, TypeError):
        return []
    out = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()[:MAX_TEXT]
        if text and item.get("type") in ("must", "nice"):
            out.append({"text": text, "type": item["type"]})
    return out[:MAX_REQUIREMENTS]
