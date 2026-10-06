from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from fsp_market.db import Base


class Specialization(Base):
    __tablename__ = "specializations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))


class Competency(Base):
    __tablename__ = "competencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    specialization_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("specializations.id"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
