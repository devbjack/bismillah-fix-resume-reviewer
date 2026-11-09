from pathlib import Path

import pytest

from app.decider import MODEL_DIR, JuliaDecider

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.slow
def test_julia_separates_met_from_unmet():
    d = JuliaDecider(str(ROOT / MODEL_DIR))
    req = "3+ years of professional Python experience"
    yes = d.p_met(req, ["Backend Engineer, 2019-2024. Built Python services with Django and FastAPI."])
    no = d.p_met(req, ["Graphic designer. Adobe Illustrator, branding, print layouts."])
    assert 0.0 <= no < yes <= 1.0
