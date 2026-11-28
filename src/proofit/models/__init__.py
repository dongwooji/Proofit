"""ORM models. Import every model module here so `Base.metadata` is complete for Alembic."""

from proofit.db.base import Base

__all__ = ["Base"]
