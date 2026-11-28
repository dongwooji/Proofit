"""Pydantic I/O schemas for jobs, sources, and snapshots."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from proofit.enums import (
    DeadlineType,
    DetailStatus,
    EmploymentType,
    ExperienceLevel,
    JobStatus,
    WorkMode,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class JobSourceCreate(_Strict):
    platform: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    external_id: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2000)


class JobCreate(_Strict):
    company_name: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    location: str | None = Field(default=None, max_length=200)
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    experience_level: ExperienceLevel = ExperienceLevel.UNKNOWN
    experience_text: str | None = Field(default=None, max_length=300)
    work_mode: WorkMode = WorkMode.UNKNOWN
    deadline_type: DeadlineType = DeadlineType.UNKNOWN
    deadline_date: date | None = None
    status: JobStatus = JobStatus.UNKNOWN
    source: JobSourceCreate | None = None


class JobUpdate(_Strict):
    """Partial update; only fields that are explicitly set are applied."""

    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    location: str | None = Field(default=None, max_length=200)
    employment_type: EmploymentType | None = None
    experience_level: ExperienceLevel | None = None
    experience_text: str | None = Field(default=None, max_length=300)
    work_mode: WorkMode | None = None
    deadline_type: DeadlineType | None = None
    deadline_date: date | None = None
    status: JobStatus | None = None


class SnapshotCreate(_Strict):
    content: str = Field(min_length=1)
    content_type: str = Field(default="text/plain", max_length=100)
    source_id: int | None = None


class JobFilter(_Strict):
    q: str | None = Field(default=None, description="기업명·직무명 부분 일치")
    status: JobStatus | None = None
    employment_type: EmploymentType | None = None
    experience_level: ExperienceLevel | None = None
    seen_since: datetime | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class _Read(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class JobSourceRead(_Read):
    id: int
    job_id: int
    platform: str
    external_id: str | None
    source_url: str | None
    first_seen_at: datetime
    last_seen_at: datetime


class JobRead(_Read):
    id: int
    company_name: str
    title: str
    location: str | None
    employment_type: EmploymentType
    experience_level: ExperienceLevel
    experience_text: str | None
    work_mode: WorkMode
    deadline_type: DeadlineType
    deadline_date: date | None
    status: JobStatus
    detail_status: DetailStatus
    first_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class JobDetailRead(JobRead):
    sources: list[JobSourceRead]


class SnapshotRead(_Read):
    id: int
    job_id: int
    source_id: int | None
    content: str
    content_type: str
    content_hash: str
    collected_at: datetime
