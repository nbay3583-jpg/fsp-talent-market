"""Pure matching engine: hard constraints, Requirement Fit and structured WHY / GAPS.

No database, no LLM, no randomness. Every reason is derived from a concrete fact in
CandidateFacts / NeedSpec; nothing is generated that is not in the data. Requirement Fit
measures fit to ONE need; it is not a Talent Score.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fsp_market.common.enums import (
    SUBLEVEL_GRADE,
    SUBLEVEL_ORDER,
    Grade,
    SalaryType,
    Sublevel,
    VerificationStatus,
)
import re

from fsp_market.matching.facts import CandidateFacts, NeedSkillSpec, NeedSpec
from fsp_market.matching.policy import DEFAULT_POLICY, MatchingPolicy
from fsp_market.taxonomy.grades import GRADE_SUBLEVELS

GRADE_RANK = {Grade.JUNIOR: 0, Grade.MIDDLE: 1, Grade.SENIOR: 2}

# exclusion codes
NOT_VISIBLE = "NOT_VISIBLE"
NOT_OPEN = "NOT_OPEN_TO_INVITATIONS"
SPECIALIZATION_MISMATCH = "SPECIALIZATION_MISMATCH"
GRADE_UNKNOWN = "GRADE_UNKNOWN"
GRADE_OUT_OF_RANGE = "GRADE_OUT_OF_RANGE"
SALARY_MISMATCH = "SALARY_MISMATCH"
WORK_FORMAT_MISMATCH = "WORK_FORMAT_MISMATCH"
LOCATION_MISMATCH = "LOCATION_MISMATCH"
AVAILABILITY_MISMATCH = "AVAILABILITY_MISMATCH"


def candidate_sublevels(c: CandidateFacts) -> set[Sublevel]:
    """Verified candidates have one exact sublevel; others (and verified candidates whose
    sublevel still needs clarification) only a grade, hence its whole range of three."""
    if c.verification_status == VerificationStatus.VERIFIED and c.verified_sublevel:
        return {c.verified_sublevel}
    grade = (
        c.verified_grade
        if c.verification_status == VerificationStatus.VERIFIED and c.verified_grade
        else c.claimed_grade
    )
    return set(GRADE_SUBLEVELS[grade]) if grade else set()


def allowed_sublevels(need: NeedSpec, policy: MatchingPolicy = DEFAULT_POLICY) -> set[Sublevel]:
    """Target M1 with tolerance 1 -> {J3, M1, M2} (+-1 on the ordered J1..S3 scale; crossing a
    public-grade border only when policy.cross_grade_tolerance). Without a target sublevel: the
    grade's own three."""
    if need.target_sublevel is None:
        return set(GRADE_SUBLEVELS[need.target_grade])
    i = SUBLEVEL_ORDER.index(need.target_sublevel)
    lo, hi = max(0, i - policy.sublevel_tolerance), i + policy.sublevel_tolerance
    out = set(SUBLEVEL_ORDER[lo : hi + 1])
    if not policy.cross_grade_tolerance:
        out = {s for s in out if SUBLEVEL_GRADE[s] == SUBLEVEL_GRADE[need.target_sublevel]}
    return out


def _to_type(amount: int, src: SalaryType | None, dst: SalaryType, policy: MatchingPolicy) -> float:
    if src is None or src == dst:
        return float(amount)
    if src == SalaryType.NET:  # NET -> GROSS
        return amount / (1 - policy.ndfl_rate)
    return amount * (1 - policy.ndfl_rate)  # GROSS -> NET


def salary_compatible(need: NeedSpec, c: CandidateFacts, policy: MatchingPolicy) -> bool:
    if c.salary_min is None:
        return True  # no stated expectation: cannot exclude
    return _to_type(c.salary_min, c.salary_type, need.salary_type, policy) <= need.salary_to


def hard_filter(
    need: NeedSpec, c: CandidateFacts, policy: MatchingPolicy = DEFAULT_POLICY
) -> list[str]:
    """Returns exclusion codes; an empty list means the candidate enters scoring."""
    out: list[str] = []
    if not c.profile_visible:
        out.append(NOT_VISIBLE)
    if not c.open_to_invitations:
        out.append(NOT_OPEN)
    if c.specialization_id != need.specialization_id:
        out.append(SPECIALIZATION_MISMATCH)
    subs = candidate_sublevels(c)
    if not subs:
        out.append(GRADE_UNKNOWN)
    elif not subs & allowed_sublevels(need, policy):
        out.append(GRADE_OUT_OF_RANGE)
    if not salary_compatible(need, c, policy):
        out.append(SALARY_MISMATCH)
    shared = set(need.work_formats) & set(c.work_formats)
    if c.work_formats and not shared:
        out.append(WORK_FORMAT_MISMATCH)
    elif (
        shared
        and "REMOTE" not in shared
        and need.location
        and c.location
        and need.location.casefold() != c.location.casefold()
    ):
        out.append(LOCATION_MISMATCH)
    if (
        need.max_start_days is not None
        and c.available_in_days is not None
        and c.available_in_days > need.max_start_days
    ):
        out.append(AVAILABILITY_MISMATCH)
    return out


@dataclass(frozen=True)
class Reason:
    code: str
    text: str
    skill: str | None = None

    def as_dict(self) -> dict:
        return {"code": self.code, "text": self.text, "skill": self.skill}


@dataclass(frozen=True)
class FitResult:
    fit: float  # 0..1, fit to THIS need only
    components: dict[str, float]
    why: list[Reason]
    gaps: list[Reason]


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _freshness(latest: datetime | None, now: datetime, policy: MatchingPolicy) -> float:
    if latest is None:
        return 0.0
    age = (_aware(now) - _aware(latest)).days
    if age <= policy.freshness_full_days:
        return 1.0
    if age >= policy.freshness_zero_days:
        return 0.0
    span = policy.freshness_zero_days - policy.freshness_full_days
    return round(1.0 - (age - policy.freshness_full_days) / span, 4)


_WORD = re.compile(r"[a-zа-яё0-9+#.]{4,}", re.IGNORECASE)
_STOP = frozenset(
    "this that with from have will your about работа работы работать требуется ищем нужен "
    "опыт опыта опытом знание знания умение навыки компания команда разработчик разработка "
    "backend python developer engineer middle junior senior senior".split()
)


def _words(text: str) -> set[str]:
    return {w.lower().strip(".") for w in _WORD.findall(text)} - _STOP


def context_fit(need: NeedSpec, c: CandidateFacts, now: datetime) -> tuple[float, list[Reason]]:
    """Explainable overlap between the candidate's DECLARED jobs and the need: skills in the job
    stack (weighted by the need) and domain words shared with the vacancy text. Always labelled as
    not confirmed by the platform; it never replaces verification."""
    if not c.experience or not need.skills:
        return 0.0, []
    total_w = sum(s.weight for s in need.skills) or 1.0
    stacks = {code for e in c.experience for code in e.stack}
    hit = [s for s in need.skills if s.code in stacks]
    stack_score = sum(s.weight for s in hit) / total_w
    need_words = _words(f"{need.title} {need.description}") - {s.code.lower() for s in need.skills}
    have_words = set().union(*(_words(e.text) for e in c.experience))
    shared = sorted(need_words & have_words)
    kw_score = min(1.0, len(shared) / min(len(need_words), 5)) if need_words else 0.0
    # recent jobs count fully, jobs ended long ago lose weight (same horizon as freshness)
    latest_end = max((e.end or now.date()) for e in c.experience)
    recency = 1.0 if (now.date() - latest_end).days <= 730 else 0.5
    score = round(min(1.0, (0.7 * stack_score + 0.3 * kw_score) * recency), 4)
    reasons: list[Reason] = []
    if hit:
        job = next(e for e in c.experience if set(e.stack) & {s.code for s in hit})
        reasons.append(
            Reason(
                "CONTEXT_FIT",
                f"В заявленном опыте («{job.position}», {job.company}) совпадают технологии "
                f"вакансии: {', '.join(sorted(s.code for s in hit))} — не подтверждено платформой",
            )
        )
    if shared:
        reasons.append(
            Reason(
                "CONTEXT_TASKS",
                f"В описании задач и проектов есть слова из вакансии: {', '.join(shared[:5])} "
                "— не подтверждено платформой",
            )
        )
    if not hit and not shared:
        reasons.append(
            Reason(
                "CONTEXT_NO_OVERLAP",
                "Заявленный опыт работы не пересекается с технологиями и задачами вакансии",
            )
        )
    return score, reasons


def requirement_fit(
    need: NeedSpec,
    c: CandidateFacts,
    now: datetime,
    policy: MatchingPolicy = DEFAULT_POLICY,
) -> FitResult:
    why: list[Reason] = []
    gaps: list[Reason] = []
    verified = c.verification_status == VerificationStatus.VERIFIED

    # --- assessment / platform grade (status only; grade comes from the Core Assessment) ---
    if verified and c.verified_sublevel:
        if need.target_sublevel:
            dist = abs(
                SUBLEVEL_ORDER.index(c.verified_sublevel)
                - SUBLEVEL_ORDER.index(need.target_sublevel)
            )
        else:
            dist = 0 if c.verified_sublevel in GRADE_SUBLEVELS[need.target_grade] else 2
        assessment = {0: 1.0, 1: 0.75}.get(dist, 0.5)
        why.append(
            Reason(
                "GRADE_VERIFIED",
                f"Подтверждён уровень Backend {c.verified_grade} ({c.verified_sublevel}) "
                "по основному тестированию",
            )
        )
    else:
        assessment = 0.0
        claimed = c.claimed_grade or "не указан"
        status = (
            "не подтверждён (NOT VERIFIED)"
            if c.verification_status == VerificationStatus.NOT_VERIFIED
            else "ещё не проверялся"
        )
        gaps.append(Reason("GRADE_NOT_VERIFIED", f"Заявленный уровень {claimed} {status}"))

    # --- per-skill evidence ---
    total_w = sum(s.weight for s in need.skills) or 1.0
    cov = prof = fsp = 0.0
    latest: datetime | None = None
    ordered = sorted(need.skills, key=lambda s: (-s.weight, s.code))
    for spec in ordered:
        f = c.skills.get(spec.code)
        tag = "обязательный" if spec.required else "желательный"
        if f and f.verified_level:
            if GRADE_RANK[f.verified_level] >= GRADE_RANK[need.target_grade]:
                cov += spec.weight
                why.append(
                    Reason("SKILL_VERIFIED", f"{spec.code}: навык подтверждён ({tag})", spec.code)
                )
            else:
                cov += spec.weight * policy.skill_credit_below_target
                gaps.append(
                    Reason(
                        "SKILL_BELOW_TARGET",
                        f"{spec.code}: подтверждён уровень {f.verified_level}, ниже целевого "
                        f"{need.target_grade} ({tag})",
                        spec.code,
                    )
                )
        elif f and f.experience:
            cov += spec.weight * policy.skill_credit_experience_only
            why.append(
                Reason(
                    "SKILL_EXPERIENCE",
                    f"{spec.code}: заявлен опыт, не подтверждён ({tag})",
                    spec.code,
                )
            )
            gaps.append(
                Reason(
                    "WEAK_EVIDENCE",
                    f"{spec.code}: не подтверждён — опыт из резюме платформа не проверяла",
                    spec.code,
                )
            )
        elif f and f.claimed:
            gaps.append(
                Reason(
                    "SKILL_UNVERIFIED",
                    f"{spec.code}: навык заявлен, но не подтверждён ({tag})",
                    spec.code,
                )
            )
        else:
            gaps.append(
                Reason("SKILL_UNVERIFIED", f"{spec.code}: нет данных о навыке ({tag})", spec.code)
            )
        if f:
            if f.experience:
                prof += spec.weight
            if f.fsp_titles:
                fsp += spec.weight
                why.append(
                    Reason(
                        "FSP_RELEVANT",
                        f"Релевантное достижение ФСП ({spec.code}): {f.fsp_titles[0]}",
                        spec.code,
                    )
                )
            if (
                (f.verified_level or f.experience or f.fsp_titles)
                and f.latest_evidence_at
                and (latest is None or _aware(f.latest_evidence_at) > _aware(latest))
            ):
                latest = f.latest_evidence_at

    # --- constraints that held (facts, not scores) ---
    if c.salary_min is not None:
        why.append(
            Reason(
                "SALARY_OVERLAP",
                f"Ожидания по зарплате ({c.salary_min:,} {c.salary_type or need.salary_type}) "
                f"укладываются в вилку {need.salary_from:,}–{need.salary_to:,} {need.salary_type}",
            )
        )
    shared = sorted(set(need.work_formats) & set(c.work_formats))
    if shared:
        why.append(Reason("WORK_FORMAT_MATCH", f"Формат работы совпадает: {', '.join(shared)}"))

    ctx, ctx_reasons = context_fit(need, c, now)
    for r in ctx_reasons:
        (gaps if r.code == "CONTEXT_NO_OVERLAP" else why).append(r)
    components = {
        "context": ctx,
        "skill_coverage": round(cov / total_w, 4),
        "assessment": assessment,
        "professional": round(prof / total_w, 4),
        "fsp": round(fsp / total_w, 4),
        "freshness": _freshness(latest, now, policy),
    }
    weight_sum = sum(policy.weights[k] for k in policy.active_components)
    fit = sum(policy.weights[k] * components[k] for k in policy.active_components) / weight_sum
    if not verified:
        fit *= policy.not_verified_factor  # ranking penalty; the candidate is not removed
    return FitResult(round(fit, 4), components, why, gaps)


def need_skill_specs(
    required: dict[str, float], optional: dict[str, float]
) -> tuple[NeedSkillSpec, ...]:
    return tuple(NeedSkillSpec(c, True, w) for c, w in required.items()) + tuple(
        NeedSkillSpec(c, False, w) for c, w in optional.items()
    )
