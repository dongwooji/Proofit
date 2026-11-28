import proofit
from proofit.config import Settings


def test_package_imports() -> None:
    assert proofit.__version__


def test_default_database_is_local_sqlite() -> None:
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("sqlite:///")
    assert settings.database_url.endswith("data/proofit.db")
