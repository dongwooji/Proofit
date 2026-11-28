from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.util.exc import CommandError
from sqlalchemy import Engine, text

from proofit.db.base import UTCDateTime
from tests.conftest import alembic_config, sqlite_url


def test_sqlite_pragmas_are_applied(engine: Engine) -> None:
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_migrations_match_models(db_url: str) -> None:
    """`alembic check` fails if models changed without a migration."""
    try:
        command.check(alembic_config(db_url))
    except CommandError as exc:  # pragma: no cover - failure path
        pytest.fail(f"models and migrations differ: {exc}")


def test_migrations_downgrade_to_base_and_back(tmp_path: Path) -> None:
    cfg = alembic_config(sqlite_url(tmp_path / "roundtrip.db"))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_utc_datetime_roundtrip_and_rejects_naive() -> None:
    col = UTCDateTime()
    kst = timezone(timedelta(hours=9))
    stored = col.process_bind_param(datetime(2026, 11, 28, 9, 0, tzinfo=kst), None)  # type: ignore[arg-type]
    assert stored == datetime(2026, 11, 28, 0, 0)
    assert col.process_result_value(stored, None) == datetime(2026, 11, 28, 0, 0, tzinfo=UTC)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        col.process_bind_param(datetime(2026, 11, 28), None)  # type: ignore[arg-type]
