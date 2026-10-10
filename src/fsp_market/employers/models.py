from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from fsp_market.auth.credentials import CredentialsMixin
from fsp_market.db import Base


class Employer(CredentialsMixin, Base):
    __tablename__ = "employers"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255))
    contact_email: Mapped[str] = mapped_column(String(255), unique=True)
