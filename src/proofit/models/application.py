"""Application tracking: current status per job plus an append-only event log."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from proofit.db.base import Base, UTCDateTime, str_enum, utcnow
from proofit.enums import ApplicationStatus
from proofit.models.job import Job


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Job 1 : 0..1 Application
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, index=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        str_enum(ApplicationStatus, "application_status"), index=True
    )
    # Set when the application first enters APPLIED.
    applied_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    job: Mapped[Job] = relationship()
    events: Mapped[list[ApplicationEvent]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationEvent.id",
    )


class ApplicationEvent(Base):
    """One status transition. Rows are immutable (UPDATE blocked by trigger)."""

    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    # NULL for the event that creates the application.
    from_status: Mapped[ApplicationStatus | None] = mapped_column(
        str_enum(ApplicationStatus, "from_status")
    )
    to_status: Mapped[ApplicationStatus] = mapped_column(str_enum(ApplicationStatus, "to_status"))
    # True when the user overrode the normal transition rules to fix a mistake.
    is_correction: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    application: Mapped[Application] = relationship(back_populates="events")
