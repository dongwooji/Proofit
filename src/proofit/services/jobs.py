"""Job CRUD, source registration, and immutable snapshots."""

from __future__ import annotations

import hashlib
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from proofit.db.base import utcnow
from proofit.enums import DeadlineType, DetailStatus
from proofit.errors import ConflictError, NotFoundError, ValidationError
from proofit.models.job import Job, JobSnapshot, JobSource
from proofit.schemas.jobs import (
    JobCreate,
    JobFilter,
    JobSourceCreate,
    JobUpdate,
    SnapshotCreate,
)

_NON_NULLABLE_FIELDS = {
    "company_name",
    "title",
    "employment_type",
    "experience_level",
    "work_mode",
    "deadline_type",
    "status",
}


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _check_deadline(deadline_type: DeadlineType, deadline_date: date | None) -> None:
    if deadline_type == DeadlineType.DATE and deadline_date is None:
        raise ValidationError("마감일 유형이 '날짜'이면 마감일을 입력해야 합니다.")
    if deadline_type != DeadlineType.DATE and deadline_date is not None:
        raise ValidationError("마감일은 마감일 유형이 '날짜'일 때만 입력할 수 있습니다.")


def get_job(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise NotFoundError(f"공고(id={job_id})를 찾을 수 없습니다.")
    return job


def find_job_by_source(session: Session, platform: str, external_id: str) -> Job | None:
    stmt = (
        select(Job)
        .join(JobSource)
        .where(JobSource.platform == platform, JobSource.external_id == external_id)
    )
    return session.scalars(stmt).first()


def create_job(session: Session, data: JobCreate) -> Job:
    _check_deadline(data.deadline_type, data.deadline_date)
    job = Job(**data.model_dump(exclude={"source"}))
    session.add(job)
    if data.source is not None:
        _ensure_source_unique(session, data.source)
        job.sources.append(JobSource(**data.source.model_dump()))
    session.flush()
    return job


def update_job(session: Session, job_id: int, data: JobUpdate) -> Job:
    job = get_job(session, job_id)
    changes = data.model_dump(exclude_unset=True)
    for field in _NON_NULLABLE_FIELDS & changes.keys():
        if changes[field] is None:
            raise ValidationError(f"'{field}' 값은 비울 수 없습니다.")
    # Switching away from DATE without saying otherwise clears the stale date.
    if (
        "deadline_type" in changes
        and "deadline_date" not in changes
        and changes["deadline_type"] != DeadlineType.DATE
    ):
        changes["deadline_date"] = None
    _check_deadline(
        changes.get("deadline_type", job.deadline_type),
        changes.get("deadline_date", job.deadline_date),
    )
    for field, value in changes.items():
        setattr(job, field, value)
    session.flush()
    return job


def list_jobs(session: Session, flt: JobFilter) -> list[Job]:
    stmt = select(Job)
    if flt.q:
        pattern = f"%{flt.q}%"
        stmt = stmt.where(or_(Job.company_name.ilike(pattern), Job.title.ilike(pattern)))
    if flt.status is not None:
        stmt = stmt.where(Job.status == flt.status)
    if flt.employment_type is not None:
        stmt = stmt.where(Job.employment_type == flt.employment_type)
    if flt.experience_level is not None:
        stmt = stmt.where(Job.experience_level == flt.experience_level)
    if flt.seen_since is not None:
        stmt = stmt.where(Job.first_seen_at >= flt.seen_since)
    stmt = stmt.order_by(Job.first_seen_at.desc(), Job.id.desc())
    return list(session.scalars(stmt.limit(flt.limit).offset(flt.offset)))


def _ensure_source_unique(session: Session, data: JobSourceCreate) -> None:
    if data.external_id is None:
        return
    existing = find_job_by_source(session, data.platform, data.external_id)
    if existing is not None:
        raise ConflictError(
            f"이미 등록된 출처입니다: {data.platform} / {data.external_id} (공고 id={existing.id})"
        )


def add_source(session: Session, job_id: int, data: JobSourceCreate) -> JobSource:
    job = get_job(session, job_id)
    _ensure_source_unique(session, data)
    source = JobSource(**data.model_dump())
    job.sources.append(source)
    session.flush()
    return source


def add_snapshot(session: Session, job_id: int, data: SnapshotCreate) -> tuple[JobSnapshot, bool]:
    """Store JD text if it is new for this job. Returns (snapshot, created)."""
    job = get_job(session, job_id)
    if data.source_id is not None:
        source = session.get(JobSource, data.source_id)
        if source is None or source.job_id != job.id:
            raise ValidationError("스냅샷의 출처가 이 공고에 속하지 않습니다.")
    digest = content_hash(data.content)
    existing = session.scalars(
        select(JobSnapshot).where(JobSnapshot.job_id == job.id, JobSnapshot.content_hash == digest)
    ).first()
    if existing is not None:
        return existing, False
    snapshot = JobSnapshot(
        source_id=data.source_id,
        content=data.content,
        content_type=data.content_type,
        content_hash=digest,
        collected_at=utcnow(),
    )
    job.snapshots.append(snapshot)
    session.flush()
    return snapshot, True


def mark_detail_verified(session: Session, job_id: int) -> Job:
    job = get_job(session, job_id)
    if not job.snapshots:
        raise ValidationError("상세 JD 스냅샷이 없는 공고는 '상세 확보'로 표시할 수 없습니다.")
    job.detail_status = DetailStatus.DETAIL_VERIFIED
    session.flush()
    return job


def list_snapshots(session: Session, job_id: int) -> list[JobSnapshot]:
    return list(get_job(session, job_id).snapshots)
