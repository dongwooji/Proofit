"""Candidate profile, projects, and versioned evidence.

Editing evidence never mutates a version: it appends a new one. Only confirmed
versions may be used in evaluation.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from proofit.db.base import utcnow
from proofit.enums import AI_EXTRACTED_ORIGINS, EvidenceOrigin, ReviewStatus
from proofit.errors import ConflictError, NotFoundError, ValidationError
from proofit.models.candidate import CandidateProfile, EvidenceItem, EvidenceItemVersion, Project
from proofit.schemas.candidate import (
    EvidenceContent,
    EvidenceCreate,
    EvidenceUpdate,
    ProfileUpdate,
    ProjectCreate,
    ProjectUpdate,
)

_CONTENT_FIELDS = tuple(EvidenceContent.model_fields)
_PROJECT_NON_NULLABLE = {"kind", "title"}


# --- profile (single user) ---------------------------------------------------


def get_or_create_profile(session: Session) -> CandidateProfile:
    profile = session.scalars(select(CandidateProfile).order_by(CandidateProfile.id)).first()
    if profile is None:
        profile = CandidateProfile()
        session.add(profile)
        session.flush()
    return profile


def update_profile(session: Session, data: ProfileUpdate) -> CandidateProfile:
    profile = get_or_create_profile(session)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    session.flush()
    return profile


# --- projects ----------------------------------------------------------------


def _check_period(start: str | None, end: str | None) -> None:
    if start and end and end < start:
        raise ValidationError("종료 시기가 시작 시기보다 빠를 수 없습니다.")


def create_project(session: Session, data: ProjectCreate) -> Project:
    _check_period(data.period_start, data.period_end)
    project = Project(profile_id=get_or_create_profile(session).id, **data.model_dump())
    session.add(project)
    session.flush()
    return project


def get_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"프로젝트(id={project_id})를 찾을 수 없습니다.")
    return project


def list_projects(session: Session) -> list[Project]:
    return list(get_or_create_profile(session).projects)


def update_project(session: Session, project_id: int, data: ProjectUpdate) -> Project:
    project = get_project(session, project_id)
    changes = data.model_dump(exclude_unset=True)
    for field in _PROJECT_NON_NULLABLE & changes.keys():
        if changes[field] is None:
            raise ValidationError(f"'{field}' 값은 비울 수 없습니다.")
    _check_period(
        changes.get("period_start", project.period_start),
        changes.get("period_end", project.period_end),
    )
    for field, value in changes.items():
        setattr(project, field, value)
    session.flush()
    return project


# --- evidence ----------------------------------------------------------------


def _check_version_rules(origin: EvidenceOrigin, content: dict[str, object], confirm: bool) -> None:
    if origin in AI_EXTRACTED_ORIGINS and confirm:
        raise ValidationError(
            "AI가 추출한 증거 초안은 바로 확정할 수 없습니다. 내용을 확인한 뒤 확정해 주세요."
        )
    if origin == EvidenceOrigin.GITHUB and not (content["source_url"] and content["commit_sha"]):
        raise ValidationError("GitHub에서 뽑은 증거에는 저장소 URL과 커밋 SHA가 필요합니다.")


def _new_version(
    item: EvidenceItem,
    version_no: int,
    origin: EvidenceOrigin,
    content: dict[str, object],
    confirm: bool,
) -> EvidenceItemVersion:
    _check_version_rules(origin, content, confirm)
    now = utcnow()
    version = EvidenceItemVersion(
        version_no=version_no,
        origin=origin,
        review_status=ReviewStatus.CONFIRMED if confirm else ReviewStatus.DRAFT,
        confirmed_at=now if confirm else None,
        created_at=now,
        **content,
    )
    item.versions.append(version)
    return version


def create_evidence(session: Session, data: EvidenceCreate) -> EvidenceItem:
    profile = get_or_create_profile(session)
    if data.project_id is not None:
        get_project(session, data.project_id)
    item = EvidenceItem(profile_id=profile.id, project_id=data.project_id, kind=data.kind)
    session.add(item)
    _new_version(item, 1, data.origin, data.model_dump(include=set(_CONTENT_FIELDS)), data.confirm)
    session.flush()
    return item


def get_evidence(session: Session, item_id: int) -> EvidenceItem:
    item = session.get(EvidenceItem, item_id)
    if item is None:
        raise NotFoundError(f"증거(id={item_id})를 찾을 수 없습니다.")
    return item


def list_evidence(session: Session, project_id: int | None = None) -> list[EvidenceItem]:
    stmt = select(EvidenceItem).order_by(EvidenceItem.id)
    if project_id is not None:
        stmt = stmt.where(EvidenceItem.project_id == project_id)
    return list(session.scalars(stmt))


def update_evidence(session: Session, item_id: int, data: EvidenceUpdate) -> EvidenceItemVersion:
    """Append a new version built from the current one plus the given changes."""
    item = get_evidence(session, item_id)
    current = item.current_version
    changes = data.model_dump(exclude_unset=True, exclude={"confirm", "origin"})
    if "claim" in changes and changes["claim"] is None:
        raise ValidationError("증거 내용(claim)은 비울 수 없습니다.")
    if "skills" in changes and changes["skills"] is None:
        changes["skills"] = []
    content = {field: getattr(current, field) for field in _CONTENT_FIELDS} | changes
    origin = data.origin or current.origin
    unchanged = all(getattr(current, f) == content[f] for f in _CONTENT_FIELDS)
    if unchanged and origin == current.origin:
        raise ValidationError("변경된 내용이 없습니다.")
    version = _new_version(item, current.version_no + 1, origin, content, data.confirm)
    session.flush()
    return version


def get_version(session: Session, version_id: int) -> EvidenceItemVersion:
    version = session.get(EvidenceItemVersion, version_id)
    if version is None:
        raise NotFoundError(f"증거 버전(id={version_id})을 찾을 수 없습니다.")
    return version


def list_versions(session: Session, item_id: int) -> list[EvidenceItemVersion]:
    return list(get_evidence(session, item_id).versions)


def confirm_version(session: Session, version_id: int) -> EvidenceItemVersion:
    version = get_version(session, version_id)
    if version.review_status == ReviewStatus.CONFIRMED:
        raise ConflictError("이미 확정된 증거 버전입니다.")
    version.review_status = ReviewStatus.CONFIRMED
    version.confirmed_at = utcnow()
    session.flush()
    return version


def latest_confirmed_version(item: EvidenceItem) -> EvidenceItemVersion | None:
    for version in reversed(item.versions):
        if version.review_status == ReviewStatus.CONFIRMED:
            return version
    return None


def list_confirmed_evidence(session: Session) -> list[EvidenceItemVersion]:
    """Latest confirmed version of every item: the only evidence usable in evaluation."""
    versions = (latest_confirmed_version(item) for item in list_evidence(session))
    return [v for v in versions if v is not None]
