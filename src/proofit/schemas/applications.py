"""Pydantic I/O schemas for applications and their status events."""

from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from proofit.enums import ApplicationStatus


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ApplicationCreate(_Strict):
    job_id: int
    status: ApplicationStatus = ApplicationStatus.REVIEWING
    note: str | None = None


class ApplicationUpdate(_Strict):
    note: str | None = None


class StatusChange(_Strict):
    to_status: ApplicationStatus
    note: str | None = Field(default=None, max_length=1000)
    # Override the transition rules to fix a mistake; requires a note.
    correction: bool = False
    # When it actually happened (e.g. recording yesterday's interview). Defaults to now.
    occurred_at: AwareDatetime | None = None


class _Read(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ApplicationEventRead(_Read):
    id: int
    application_id: int
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    is_correction: bool
    note: str | None
    occurred_at: datetime
    recorded_at: datetime


class ApplicationRead(_Read):
    id: int
    job_id: int
    status: ApplicationStatus
    applied_at: datetime | None
    note: str | None
    created_at: datetime
    updated_at: datetime
