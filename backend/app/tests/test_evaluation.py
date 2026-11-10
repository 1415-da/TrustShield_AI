"""Every seeded evaluation case must pass through the real gateway (offline mock provider)."""

import pytest
from sqlalchemy import select

from app.models import TestCase
from app.seed.data import TEST_CASES
from app.services import evaluation


@pytest.mark.parametrize("code", [tc["code"] for tc in TEST_CASES])
def test_seeded_case(db, code):
    tc = db.scalar(select(TestCase).where(TestCase.code == code))
    result = evaluation.run_case(db, tc)
    assert result["passed"], f"{code} '{tc.prompt}': {result['failure_reason']}"
    assert not result["false_negative"]
