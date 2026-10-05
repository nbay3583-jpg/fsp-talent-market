from sqlalchemy import Engine, text

from fsp_market.db import (
    check_database,
    make_engine,
    make_session_factory,
)


def test_make_engine_returns_sqlite_engine() -> None:
    engine: Engine = make_engine("sqlite://")
    assert engine.dialect.name == "sqlite"


def test_check_database_returns_true_for_sqlite() -> None:
    engine: Engine = make_engine("sqlite://")
    assert check_database(engine) is True


def test_check_database_returns_false_for_postgresql() -> None:
    engine: Engine = make_engine("postgresql+psycopg://x:y@127.0.0.1:1/z")
    assert check_database(engine) is False


def test_session_can_execute_select_one() -> None:
    engine: Engine = make_engine("sqlite://")
    session_factory = make_session_factory(engine)
    with session_factory() as session:
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1
