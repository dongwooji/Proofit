"""Pydantic I/O schemas for the candidate profile, projects, and evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from proofit.enums import EvidenceKind, EvidenceOrigin, ReviewStatus

_YEAR_MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"
_COMMIT_SHA = r"^[0-9a-f]{7,40}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _clean_skills(skills: list[str]) -> list[str]:
    seen: list[str] = []
    for skill in (s.strip() for s in skills):
        if skill and skill not in seen:
            seen.append(skill)
    return seen


# Trimmed, de-duplicated, order-preserving skill names.
Skills = Annotated[list[str], AfterValidator(_clean_skills)]


class ProfileUpdate(_Strict):
    display_name: str | None = Field(default=None, max_length=100)


class ProjectCreate(_Strict):
    kind: EvidenceKind = EvidenceKind.PROJECT
    title: str = Field(min_length=1, max_length=300)
    organization: str | None = Field(default=None, max_length=200)
    my_role: str | None = None
    team_size: int | None = Field(default=None, ge=1)
    period_start: str | None = Field(default=None, pattern=_YEAR_MONTH)
    period_end: str | None = Field(default=None, pattern=_YEAR_MONTH)
    url: str | None = Field(default=None, max_length=2000)
    summary: str | None = None


class ProjectUpdate(_Strict):
    kind: EvidenceKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    organization: str | None = Field(default=None, max_length=200)
    my_role: str | None = None
    team_size: int | None = Field(default=None, ge=1)
    period_start: str | None = Field(default=None, pattern=_YEAR_MONTH)
    period_end: str | None = Field(default=None, pattern=_YEAR_MONTH)
    url: str | None = Field(default=None, max_length=2000)
    summary: str | None = None


class EvidenceContent(_Strict):
    """Versioned content fields shared by create and update."""

    claim: str = Field(min_length=1)
    skills: Skills = Field(default_factory=list)
    metric: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2000)
    source_ref: str | None = Field(default=None, max_length=500)
    commit_sha: str | None = Field(default=None, pattern=_COMMIT_SHA)


class EvidenceCreate(EvidenceContent):
    kind: EvidenceKind
    project_id: int | None = None
    origin: EvidenceOrigin = EvidenceOrigin.MANUAL
    # User-authored evidence may be confirmed at once; AI-extracted drafts may not.
    confirm: bool = False


class EvidenceUpdate(_Strict):
    """Partial content change. Unset fields are copied from the current version."""

    claim: str | None = Field(default=None, min_length=1)
    skills: Skills | None = None
    metric: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2000)
    source_ref: str | None = Field(default=None, max_length=500)
    commit_sha: str | None = Field(default=None, pattern=_COMMIT_SHA)
    origin: EvidenceOrigin | None = None
    confirm: bool = False


class _Read(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProfileRead(_Read):
    id: int
    display_name: str | None
    created_at: datetime
    updated_at: datetime


class ProjectRead(_Read):
    id: int
    profile_id: int
    kind: EvidenceKind
    title: str
    organization: str | None
    my_role: str | None
    team_size: int | None
    period_start: str | None
    period_end: str | None
    url: str | None
    summary: str | None
    created_at: datetime
    updated_at: datetime


class EvidenceVersionRead(_Read):
    id: int
    item_id: int
    version_no: int
    claim: str
    skills: list[str]
    metric: str | None
    source_url: str | None
    source_ref: str | None
    commit_sha: str | None
    origin: EvidenceOrigin
    review_status: ReviewStatus
    confirmed_at: datetime | None
    created_at: datetime


class EvidenceRead(_Read):
    id: int
    profile_id: int
    project_id: int | None
    kind: EvidenceKind
    created_at: datetime
    current_version: EvidenceVersionRead
