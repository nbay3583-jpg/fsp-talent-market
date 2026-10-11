"""WHY/GAPS texts must be human-readable and must not present unverified claims as evidence."""

from tests.test_phase4_matching import NOW, cand, need

from fsp_market.common.enums import Grade, VerificationStatus
from fsp_market.matching import engine as eng
from fsp_market.matching.facts import SkillFacts


def _texts(r):
    return " | ".join(x.text for x in r.why + r.gaps)


def test_no_technical_enum_values_in_reasons():
    r = eng.requirement_fit(need(), cand(), NOW)
    text = _texts(r)
    for raw in ("REMOTE", "GROSS", "NET", "NOT VERIFIED", "MIDDLE", "api_fastapi"):
        assert raw not in text
    assert "удалённо" in text and "до налогов" in text


def test_unverified_grade_is_a_gap_in_plain_russian():
    c = cand(verification_status=VerificationStatus.NOT_VERIFIED, verified_grade=None,
             verified_sublevel=None, claimed_grade=Grade.SENIOR)
    r = eng.requirement_fit(need(), c, NOW)
    gap = next(g for g in r.gaps if g.code == "GRADE_NOT_VERIFIED")
    assert "Senior" in gap.text and "не подтверждён тестом" in gap.text
    assert not any(w.code == "GRADE_VERIFIED" for w in r.why)


def test_claimed_experience_is_not_a_verified_reason():
    skills = {"api_fastapi": SkillFacts(code="api_fastapi", experience=True, claimed=True)}
    r = eng.requirement_fit(need(), cand(skills=skills), NOW)
    assert not any(w.code == "SKILL_VERIFIED" for w in r.why)
    assert any(g.code == "WEAK_EVIDENCE" for g in r.gaps)
