from typing import Protocol

MODEL_DIR = "models/Julia-1"  # relative to the repo root


class Decider(Protocol):
    def p_met(self, requirement: str, evidence: list[str]) -> float: ...


class JuliaDecider:
    def __init__(self, model_dir: str, device: str = "cpu"):
        from julia import load_model  # installed from models/Julia-1 by scripts/download_models.py

        self.engine = load_model(model_dir, device=device, strict_encoding=True,
                                 max_length=2048, head_length=512)

    def p_met(self, requirement: str, evidence: list[str]) -> float:
        result = self.engine.predict(
            state="\n\n".join(evidence),
            questions={"met": {
                "type": "noul",
                "instructions": f"Does the candidate meet this requirement: {requirement}?",
                "criteria": {
                    "false": "The text does not show the candidate meets this requirement",
                    "true": "The text shows the candidate meets this requirement",
                },
            }},
        )
        return float(result["answers"]["met"]["noul"])
