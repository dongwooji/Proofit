"""Test fixtures.

The schema is built by running the real Alembic migrations once per test session
into a template SQLite file; each test gets its own copy of that file.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from proofit.config import PROJECT_ROOT
from proofit.db.session import create_db_engine, make_session_factory


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def alembic_config(url: str) -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("template") / "template.db"
    command.upgrade(alembic_config(sqlite_url(path)), "head")
    # Fold the WAL back into the main file so a plain file copy is complete.
    engine = create_db_engine(sqlite_url(path))
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    engine.dispose()
    return path


@pytest.fixture
def db_url(migrated_template: Path, tmp_path: Path) -> str:
    path = tmp_path / "test.db"
    shutil.copyfile(migrated_template, path)
    return sqlite_url(path)


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    eng = create_db_engine(db_url)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with make_session_factory(engine)() as s:
        yield s
