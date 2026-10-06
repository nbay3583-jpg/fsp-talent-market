from datetime import UTC

from fsp_market.common.ids import new_id, utcnow


def test_new_id_is_unique_text() -> None:
    a, b = new_id(), new_id()
    assert isinstance(a, str) and len(a) == 36 and a != b


def test_utcnow_is_timezone_aware_utc() -> None:
    assert utcnow().tzinfo is UTC
