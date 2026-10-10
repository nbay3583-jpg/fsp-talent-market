from enum import StrEnum


class Grade(StrEnum):
    JUNIOR = "JUNIOR"
    MIDDLE = "MIDDLE"
    SENIOR = "SENIOR"


class Sublevel(StrEnum):
    """Three internal sublevels per public grade: 1 = beginning, 2 = confident, 3 = advanced."""

    J1 = "J1"
    J2 = "J2"
    J3 = "J3"
    M1 = "M1"
    M2 = "M2"
    M3 = "M3"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"


# The ordered scale J1 -> ... -> S3 (the single source of truth for "neighbouring" sublevels).
SUBLEVEL_ORDER: tuple[Sublevel, ...] = tuple(Sublevel)

SUBLEVEL_GRADE: dict[Sublevel, Grade] = {
    Sublevel.J1: Grade.JUNIOR,
    Sublevel.J2: Grade.JUNIOR,
    Sublevel.J3: Grade.JUNIOR,
    Sublevel.M1: Grade.MIDDLE,
    Sublevel.M2: Grade.MIDDLE,
    Sublevel.M3: Grade.MIDDLE,
    Sublevel.S1: Grade.SENIOR,
    Sublevel.S2: Grade.SENIOR,
    Sublevel.S3: Grade.SENIOR,
}


class VerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"  # no assessment completed yet
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"


class EvidenceType(StrEnum):
    CORE_ASSESSMENT = "CORE_ASSESSMENT"
    TECHNOLOGY_ASSESSMENT = "TECHNOLOGY_ASSESSMENT"
    PROFESSIONAL_EXPERIENCE = "PROFESSIONAL_EXPERIENCE"
    FSP_ACHIEVEMENT = "FSP_ACHIEVEMENT"
    RECENT_CHALLENGE = "RECENT_CHALLENGE"


class EvidenceStrength(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TaskFormat(StrEnum):
    DETERMINISTIC_QUESTION = "DETERMINISTIC_QUESTION"
    CODE_READING = "CODE_READING"
    SQL_REASONING = "SQL_REASONING"
    API_REASONING = "API_REASONING"
    RUBRIC_CHECK = "RUBRIC_CHECK"
    BUG_HUNT = "BUG_HUNT"
    MULTI_SELECT = "MULTI_SELECT"
    NUMERIC_ANSWER = "NUMERIC_ANSWER"
    ARCHITECTURE_CASE = "ARCHITECTURE_CASE"


class AttemptStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    SCORED = "SCORED"


class Competency(StrEnum):
    """Core Assessment competencies of the Backend / Python track (plan section 10)."""

    PYTHON = "PYTHON"
    SQL = "SQL"
    API_FASTAPI = "API_FASTAPI"
    TESTING = "TESTING"
    DOCKER_BASICS = "DOCKER_BASICS"
    SYSTEM_THINKING = "SYSTEM_THINKING"


class AssessmentKind(StrEnum):
    CORE = "CORE"  # the only mechanism that sets the platform grade
    TECHNOLOGY = "TECHNOLOGY"  # depth of one technology: extra evidence, never the grade


class AssessmentOutcome(StrEnum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"


class ClaimSource(StrEnum):
    RESUME = "RESUME"
    MANUAL_PROFILE = "MANUAL_PROFILE"
    SELECTED_SKILL = "SELECTED_SKILL"


class UserRole(StrEnum):
    CANDIDATE = "CANDIDATE"
    EMPLOYER = "EMPLOYER"
    ADMIN = "ADMIN"


class WorkFormat(StrEnum):
    REMOTE = "REMOTE"
    OFFICE = "OFFICE"
    HYBRID = "HYBRID"


class SalaryType(StrEnum):
    GROSS = "GROSS"
    NET = "NET"


class SkillImportance(StrEnum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"


class InvitationStatus(StrEnum):
    SENT = "SENT"
    VIEWED = "VIEWED"
    ACCEPTED = "ACCEPTED"
    CONTACTS_UNLOCKED = "CONTACTS_UNLOCKED"
    DECLINED = "DECLINED"
