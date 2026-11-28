"""Candidate profile, projects, and versioned evidence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from proofit.db.base import Base, UTCDateTime, str_enum, utcnow
from proofit.enums import EvidenceKind, EvidenceOrigin, ReviewStatus


class CandidateProfile(Base):
    """The single user. Contact details are intentionally not stored here."""

    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Used only in document drafts; never sent in evaluation payloads.
    display_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    projects: Mapped[list[Project]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", order_by="Project.id"
    )


class Project(Base):
    """Context that groups evidence: a project, paper, job, or research experience."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[EvidenceKind] = mapped_column(str_enum(EvidenceKind, "project_kind"))
    title: Mapped[str] = mapped_column(String(300))
    organization: Mapped[str | None] = mapped_column(String(200))
    my_role: Mapped[str | None] = mapped_column(Text)
    team_size: Mapped[int | None]
    period_start: Mapped[str | None] = mapped_column(String(7))  # YYYY-MM
    period_end: Mapped[str | None] = mapped_column(String(7))  # YYYY-MM; NULL = ongoing
    url: Mapped[str | None] = mapped_column(String(2000))
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    profile: Mapped[CandidateProfile] = relationship(back_populates="projects")


class EvidenceItem(Base):
    """Identity of one piece of evidence. Content lives in immutable versions.

    The current version is the one with the highest `version_no` (no stored pointer,
    so it cannot drift out of sync).
    """

    __tablename__ = "evidence_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[EvidenceKind] = mapped_column(str_enum(EvidenceKind, "evidence_kind"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    project: Mapped[Project | None] = relationship()
    versions: Mapped[list[EvidenceItemVersion]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="EvidenceItemVersion.version_no",
    )

    @property
    def current_version(self) -> EvidenceItemVersion:
        return self.versions[-1]


class EvidenceItemVersion(Base):
    """Immutable content of an evidence item at one point in time.

    Only the one-way review step (DRAFT -> CONFIRMED, setting confirmed_at) may
    update a row; DB triggers reject any other UPDATE.
    """

    __tablename__ = "evidence_item_versions"
    __table_args__ = (UniqueConstraint("item_id", "version_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_items.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int]
    claim: Mapped[str] = mapped_column(Text)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    metric: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(2000))
    # Where in the source the claim is supported, e.g. "README", "notebooks/eval.ipynb".
    source_ref: Mapped[str | None] = mapped_column(String(500))
    commit_sha: Mapped[str | None] = mapped_column(String(40))
    origin: Mapped[EvidenceOrigin] = mapped_column(str_enum(EvidenceOrigin, "evidence_origin"))
    review_status: Mapped[ReviewStatus] = mapped_column(
        str_enum(ReviewStatus, "review_status"), default=ReviewStatus.DRAFT
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    item: Mapped[EvidenceItem] = relationship(back_populates="versions")
