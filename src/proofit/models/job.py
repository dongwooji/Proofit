"""Job postings: normalized job, its sources, and immutable JD snapshots."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from proofit.db.base import Base, UTCDateTime, str_enum, utcnow
from proofit.enums import (
    DeadlineType,
    DetailStatus,
    EmploymentType,
    ExperienceLevel,
    JobStatus,
    WorkMode,
)


class Job(Base):
    """One real-world position, possibly discovered through several sources."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "(deadline_type = 'DATE') = (deadline_date IS NOT NULL)",
            name="deadline_date_matches_type",
        ),
        Index("ix_jobs_company_title", "company_name", "title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(200))
    employment_type: Mapped[EmploymentType] = mapped_column(
        str_enum(EmploymentType, "employment_type"), default=EmploymentType.UNKNOWN
    )
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        str_enum(ExperienceLevel, "experience_level"), default=ExperienceLevel.UNKNOWN
    )
    # Source wording of the experience condition, e.g. "경력 3년 이상 우대".
    experience_text: Mapped[str | None] = mapped_column(String(300))
    work_mode: Mapped[WorkMode] = mapped_column(
        str_enum(WorkMode, "work_mode"), default=WorkMode.UNKNOWN
    )
    deadline_type: Mapped[DeadlineType] = mapped_column(
        str_enum(DeadlineType, "deadline_type"), default=DeadlineType.UNKNOWN
    )
    deadline_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[JobStatus] = mapped_column(
        str_enum(JobStatus, "job_status"), default=JobStatus.UNKNOWN, index=True
    )
    detail_status: Mapped[DetailStatus] = mapped_column(
        str_enum(DetailStatus, "detail_status"), default=DetailStatus.LISTING_ONLY
    )
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    sources: Mapped[list[JobSource]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobSource.id"
    )
    snapshots: Mapped[list[JobSnapshot]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobSnapshot.id"
    )


class JobSource(Base):
    """Where a job was found: platform, external ID, and URL."""

    __tablename__ = "job_sources"
    __table_args__ = (UniqueConstraint("platform", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    # Provider key such as "rocketpunch", "greenhouse", "manual".
    platform: Mapped[str] = mapped_column(String(50))
    # Platform's own posting ID; NULL for manual entries (SQLite allows many NULLs).
    external_id: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(2000))
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="sources")


class JobSnapshot(Base):
    """Immutable JD text as collected. UPDATE is blocked by a DB trigger."""

    __tablename__ = "job_snapshots"
    __table_args__ = (UniqueConstraint("job_id", "content_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("job_sources.id"))
    content: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(100), default="text/plain")
    # SHA-256 hex of the UTF-8 bytes of `content`, exactly as stored.
    content_hash: Mapped[str] = mapped_column(String(64))
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="snapshots")
