from __future__ import annotations

from functools import lru_cache
from typing import Generator

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from fsp_market.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_settings().database_url, pool_pre_ping=True)


def make_session_factory(engine: Engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def check_database(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True


@lru_cache
def get_engine() -> Engine:
    return make_engine()


def get_session() -> Generator[Session, None, None]:
    session = make_session_factory(get_engine())()
    try:
        yield session
    finally:
        session.close()


from sqlalchemy import create_engine


__all__ = [
    "Base",
    "check_database",
    "get_engine",
    "get_session",
    "make_engine",
    "make_session_factory",
]
