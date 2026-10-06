import json
import math
from pathlib import Path

import pytest

from fsp_market.validation import assessment as av
from fsp_market.validation import constraints, dataset, metrics
from fsp_market.validation.matching import keyword_ranking
from fsp_market.validation.runner import run_validation

ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts" / "validation" / "latest.json"

# ------------------------------------------------------------------ metrics


def test_precision_uses_k_as_denominator():
    assert metrics.precision_at_k(["a", "b", "c"], {"a", "c"}, 3) == pytest.approx(2 / 3)
    assert metrics.precision_at_k(["a"], {"a"}, 5) == pytest.approx(
        1 / 5
    )  # short list is penalised
    assert metrics.precision_at_k([], {"a"}, 3) == 0.0


def test_recall_and_undefined_case():
    assert metrics.recall_at_k(["a", "x", "c"], {"a", "c", "d", "e"}, 3) == pytest.approx(2 / 4)
    assert metrics.recall_at_k(["a"], {"a"}, 10) == 1.0
    with pytest.raises(ValueError):
        metrics.recall_at_k(["a"], set(), 3)


def test_ndcg_known_miniature_example():
    grades = {"a": 3, "b": 0, "c": 2}
    dcg = 7 / math.log2(2) + 0 + 3 / math.log2(4)  # 8.5
    ideal = 7 / math.log2(2) + 3 / math.log2(3)
    assert metrics.dcg_at_k(["a", "b", "c"], grades, 3) == pytest.approx(dcg)
    assert metrics.ndcg_at_k(["a", "b", "c"], grades, 3) == pytest.approx(dcg / ideal)
    assert metrics.ndcg_at_k(["a", "c", "b"], grades, 3) == pytest.approx(1.0)
    assert metrics.ndcg_at_k(["z"], grades, 3) == 0.0
    assert (
        metrics.ndcg_at_k(["a"], {"a": 0}, 3) == 0.0
    )  # no gain anywhere -> 0, not a division error


# ------------------------------------------------------------------ constraints / baseline


NEED = {
    "specialization": "backend_python",
    "target_grade": "MIDDLE",
    "target_sublevel": "M2",
    "salary_to": 250000,
    "salary_type": "GROSS",
    "work_formats": ["REMOTE"],
    "location": None,
    "max_start_days": None,
}
CAND = {
    "specialization": "backend_python",
    "claimed_grade": "MIDDLE",
    "profile_visible": True,
    "open_to_invitations": True,
    "salary": {"min": 220000, "type": "GROSS"},
    "work_formats": ["REMOTE"],
    "location": "Moscow",
    "available_in_days": 0,
}


def test_independent_checker_detects_each_violation():
    assert constraints.violations(NEED, CAND, "M2") == []
    assert constraints.violations(
        NEED, {**CAND, "salary": {"min": 250001, "type": "GROSS"}}, "M2"
    ) == ["salary"]
    assert (
        constraints.violations(NEED, {**CAND, "salary": {"min": 217500, "type": "NET"}}, "M2") == []
    )
    assert constraints.violations(NEED, {**CAND, "work_formats": ["OFFICE"]}, "M2") == [
        "work_format"
    ]
    assert constraints.violations(NEED, {**CAND, "specialization": "frontend_ts"}, "M2") == [
        "specialization"
    ]
    assert constraints.violations(NEED, CAND, "J2") == ["grade"]
    assert constraints.violations(NEED, CAND, "S1") == []  # +-1 SUBLEVEL, M2 -> M1/M2/S1
    assert constraints.violations(NEED, CAND, "S2") == ["grade"]
    assert constraints.violations(NEED, {**CAND, "profile_visible": False}, "M2") == ["not_visible"]


def test_keyword_baseline_ignores_verification_and_constraints():
    need = {"required_skills": ["api_fastapi"], "optional_skills": ["kafka"]}
    cands = [
        {"id": "b", "resume_keywords": ["fastapi"]},
        {"id": "a", "resume_keywords": ["fastapi", "kafka"]},
        {"id": "c", "resume_keywords": ["fastapi"]},
        {"id": "z", "resume_keywords": ["react"]},
    ]
    assert keyword_ranking(need, cands) == ["a", "b", "c"]  # score desc, then id; no-hit omitted


# ------------------------------------------------------------------ dataset / labels


def test_dataset_loading_is_deterministic_and_consistent():
    a, b = dataset.load_dataset(), dataset.load_dataset()
    assert a == b and dataset.dataset_sha256() == dataset.dataset_sha256()
    cands, needs, labels = a
    assert 20 <= len(cands) <= 40 and 8 <= len(needs) <= 12
    cand_ids = {c["id"] for c in cands}
    assert len(cand_ids) == len(cands) and len({n["id"] for n in needs}) == len(needs)
    assert set(labels["labels"]) == {n["id"] for n in needs}
    for need_id, row in labels["labels"].items():
        assert set(row) <= cand_ids
        grades = dataset.relevance_grades(labels, need_id)
        assert all(0 <= g <= 3 for g in grades.values())
        assert any(g >= labels["relevant_threshold"] for g in grades.values()), need_id
        assert all(tag in labels["tags"] for _, tag in row.values())


def test_dataset_contains_the_required_conflict_cases():
    cands, _, _ = dataset.load_dataset()
    by = {c["id"]: c for c in cands}
    assert (
        by["V-C04"]["assessment"]["wrong"] == "ALL" and len(by["V-C04"]["resume_keywords"]) >= 7
    )  # strong CV, weak test
    assert (
        by["V-C05"]["resume_keywords"] == ["python"] and by["V-C05"]["assessment"]["wrong"] == []
    )  # weak CV, strong test
    assert by["V-C02"]["fsp_disciplines"] and by["V-C03"]["fsp_disciplines"] == [
        "algorithmic_programming"
    ]
    assert not by["V-C01"]["fsp_disciplines"]  # no FSP history
    assert by["V-C06"]["salary"]["min"] > 300000 and by["V-C07"]["work_formats"] == ["OFFICE"]
    assert (
        by["V-C08"]["claimed_grade"] == "MIDDLE" and len(by["V-C08"]["assessment"]["wrong"]) == 2
    )  # NOT_VERIFIED Middle
    assert "api_fastapi" in by["V-C19"]["assessment"]["wrong"]  # missing required skill
    assert "kafka" in by["V-C11"]["experience_days_ago"] and by["V-C11"]["work_formats"] == [
        "OFFICE"
    ]  # optional stars, fails hard constraint


# ------------------------------------------------------------------ full run


@pytest.fixture(scope="module")
def result():
    return run_validation()


def test_full_run_is_reproducible_and_matches_stored_artifact(result):
    again = run_validation()
    assert json.dumps(result, sort_keys=True) == json.dumps(again, sort_keys=True)
    assert (
        result["matching"]["deterministic"] is True
        and result["assessment"]["deterministic"] is True
    )
    if ARTIFACT.exists():  # artifacts are regenerated with: python -m fsp_market.validation
        assert (
            ARTIFACT.read_text(encoding="utf-8")
            == json.dumps(result, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        )


def test_matching_methods_and_constraint_violations(result):
    s = result["matching"]["summary"]
    assert set(s) == {"keyword_baseline", "hard_filters_only", "evidence_matching"}
    assert s["evidence_matching"]["constraint_violations@10"] == 0
    assert s["hard_filters_only"]["constraint_violations@10"] == 0
    assert s["keyword_baseline"]["constraint_violations@10"] > 0  # detector really detects
    for m in s.values():
        for k in ("p@3", "p@5", "r@10", "ndcg@10"):
            assert 0.0 <= m[k] <= 1.0
    assert s["evidence_matching"]["ndcg@10"] > s["keyword_baseline"]["ndcg@10"]
    assert s["evidence_matching"]["p@5"] > s["hard_filters_only"]["p@5"]


def test_ranking_is_deterministic_and_contains_no_duplicates(result):
    for method, per in result["matching"]["rankings"].items():
        for need, ranked in per.items():
            assert len(ranked) == len(set(ranked)), (method, need)
    assert result["matching"]["sensitivity"]["default"]["top5_jaccard_vs_default"] == 1.0


def test_failure_cases_are_recorded_with_reasons(result):
    fails = result["failures"]
    assert fails and all({"id", "expected", "actual", "probable_reason"} <= set(f) for f in fails)
    assert any(f["id"].startswith("keyword_baseline:") for f in fails)


# ------------------------------------------------------------------ assessment


def test_reference_personas_are_classified_as_expected(result):
    a = result["assessment"]
    assert a["grade_accuracy"] == 1.0 and a["highest_grade_accuracy"] == 1.0
    by = {(c["persona"], c["grade"], c["rotation"]): c for c in a["outcomes"]}
    assert (
        by[("P-MIDDLE", "MIDDLE", 0)]["status"] == "VERIFIED"
        and by[("P-MIDDLE", "SENIOR", 0)]["status"] == "NOT_VERIFIED"
    )
    assert (
        by[("P-JUNIOR", "MIDDLE", 1)]["status"] == "NOT_VERIFIED"
    )  # failed Middle is not downgraded to Junior
    assert (
        by[("P-MIDDLE-HIGH", "MIDDLE", 0)]["sublevel"] == "M1"
        and by[("P-MIDDLE-LOW", "MIDDLE", 0)]["status"] == "NOT_VERIFIED"
    )
    assert by[("P-SENIOR-EDGE", "SENIOR", 1)]["sublevel"] == "S1"
    assert a["disagreement_over_one_sublevel_rate"] == 0.0


def test_variant_stability_and_deterministic_scoring(result):
    stab = result["assessment"]["variant_stability"]
    assert stab["identical_outcome_rate"] == 1.0 and stab["max_abs_score_diff"] == 0.0
    assert av.run_assessment_validation()["outcomes"] == result["assessment"]["outcomes"]


def test_grade_separation(result):
    for grade, d in result["assessment"]["discrimination"].items():
        assert d["auc_knowers_vs_others"] == 1.0 and d["margin"] > 0, grade


def test_anchor_handling_and_competency_coverage(result):
    a = result["assessment"]
    assert len(a["anchors"]) == 1
    solved = a["anchors"][0]["solved_by"]
    assert "P-MIDDLE" in solved and "P-JUNIOR" not in solved and "P-WEAK" not in solved
    cov = a["coverage"]
    assert cov["competencies_covered"] == {"JUNIOR": 2, "MIDDLE": 6, "SENIOR": 4}
    assert cov["coverage_ratio"]["MIDDLE"] == 1.0 and cov["coverage_ratio"][
        "JUNIOR"
    ] == pytest.approx(2 / 6, abs=1e-4)
    assert (
        a["guessing_baseline"]["MIDDLE"]["false_verification_rate"]
        < a["guessing_baseline"]["JUNIOR"]["false_verification_rate"]
    )


def test_rubric_check_passes_on_seed_and_detects_corruption():
    session = av._fresh_db()
    assert av._rubric_checks(session)["violations"] == 0
    variant = session.query(av.TaskVariant).first()
    variant.scoring_contract = {
        **variant.scoring_contract,
        "correct": "Z",
    }  # correct option not among options
    variant.scoring_contract = dict(variant.scoring_contract)
    session.flush()
    checks = av._rubric_checks(session)
    assert checks["violations"] >= 1 and any(
        "correct option missing" in d for d in checks["details"]
    )
    session.close()
