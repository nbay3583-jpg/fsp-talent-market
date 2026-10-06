"""FSP integration boundary. Real FSP ID / Keycloak plugs in behind FSPProvider later;
the product only ever sees these three methods."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FSPMember:
    fsp_id: str
    full_name: str
    verified: bool


@dataclass(frozen=True)
class FSPAchievement:
    achievement_id: str
    fsp_id: str
    discipline: str  # algorithmic_programming | product_programming | cybersecurity
    title: str
    year: int
    place: int | None


class FSPProvider(Protocol):
    def get_member(self, fsp_id: str) -> FSPMember | None: ...

    def get_achievements(self, fsp_id: str) -> list[FSPAchievement]: ...

    def verify_member(self, fsp_id: str) -> bool: ...


DEMO_MEMBERS = [
    FSPMember("FSP-1001", "Alexey Demo", True),
    FSPMember("FSP-2002", "Nina Newcomer", True),  # verified member, no history
    FSPMember("FSP-9999", "Unverified Person", False),
]
DEMO_ACHIEVEMENTS = [
    FSPAchievement(
        "ach-1",
        "FSP-1001",
        "algorithmic_programming",
        "FSP Algorithmic Programming Cup, finalist",
        2025,
        3,
    ),
    FSPAchievement(
        "ach-2",
        "FSP-1001",
        "product_programming",
        "FSP Product Programming Hackathon, winner",
        2026,
        1,
    ),
    FSPAchievement("ach-3", "FSP-1001", "cybersecurity", "FSP CTF, participant", 2024, None),
]


class MockFSPProvider:
    def __init__(
        self,
        members: list[FSPMember] | None = None,
        achievements: list[FSPAchievement] | None = None,
    ) -> None:
        self._members = {m.fsp_id: m for m in (DEMO_MEMBERS if members is None else members)}
        self._achievements = list(DEMO_ACHIEVEMENTS if achievements is None else achievements)

    def get_member(self, fsp_id: str) -> FSPMember | None:
        return self._members.get(fsp_id)

    def get_achievements(self, fsp_id: str) -> list[FSPAchievement]:
        return [a for a in self._achievements if a.fsp_id == fsp_id]

    def verify_member(self, fsp_id: str) -> bool:
        member = self._members.get(fsp_id)
        return member is not None and member.verified
