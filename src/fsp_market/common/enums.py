from enum import StrEnum


class Grade(StrEnum):
    JUNIOR = "JUNIOR"
    MIDDLE = "MIDDLE"
    SENIOR = "SENIOR"


class Sublevel(StrEnum):
    J1 = "J1"
    J2 = "J2"
    M1 = "M1"
    M2 = "M2"
    S1 = "S1"
    S2 = "S2"


SUBLEVEL_GRADE: dict[Sublevel, Grade] = {
    Sublevel.J1: Grade.JUNIOR,
    Sublevel.J2: Grade.JUNIOR,
    Sublevel.M1: Grade.MIDDLE,
    Sublevel.M2: Grade.MIDDLE,
    Sublevel.S1: Grade.SENIOR,
    Sublevel.S2: Grade.SENIOR,
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
