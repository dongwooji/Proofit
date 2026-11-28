from datetime import date, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from proofit.db.base import utcnow
from proofit.enums import DeadlineType, DetailStatus, EmploymentType, ExperienceLevel, JobStatus
from proofit.errors import ConflictError, NotFoundError, ValidationError
from proofit.models.job import Job, JobSnapshot
from proofit.schemas.jobs import JobCreate, JobFilter, JobSourceCreate, JobUpdate, SnapshotCreate
from proofit.services import jobs as svc


def _job(session: Session, **overrides) -> Job:
    data = {
        "company_name": "예시랩스",
        "title": "AI Agent Engineer (신입)",
        "employment_type": EmploymentType.FULL_TIME,
        "experience_level": ExperienceLevel.NEW_GRAD,
        "source": {"platform": "rocketpunch", "external_id": "123", "source_url": "https://x/1"},
    }
    data.update(overrides)
    job = svc.create_job(session, JobCreate.model_validate(data))
    session.commit()
    return job


def test_create_and_get_job_with_source(session: Session) -> None:
    job = _job(session)
    loaded = svc.get_job(session, job.id)
    assert loaded.company_name == "예시랩스"
    assert loaded.status == JobStatus.UNKNOWN
    assert loaded.detail_status == DetailStatus.LISTING_ONLY
    assert loaded.first_seen_at.tzinfo is not None
    assert [(s.platform, s.external_id) for s in loaded.sources] == [("rocketpunch", "123")]


def test_get_missing_job_raises_korean_not_found(session: Session) -> None:
    with pytest.raises(NotFoundError, match="찾을 수 없습니다"):
        svc.get_job(session, 999)


def test_duplicate_platform_external_id_is_rejected(session: Session) -> None:
    _job(session)
    with pytest.raises(ConflictError):
        _job(session, title="다른 제목")


def test_db_unique_constraint_backs_up_service_check(session: Session) -> None:
    job = _job(session)
    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.execute(
            text(
                "INSERT INTO job_sources"
                " (job_id, platform, external_id, first_seen_at, last_seen_at)"
                " VALUES (:j, 'rocketpunch', '123', '2026-01-01', '2026-01-01')"
            ),
            {"j": job.id},
        )


def test_manual_sources_without_external_id_can_repeat(session: Session) -> None:
    job = _job(session, source={"platform": "manual"})
    svc.add_source(session, job.id, JobSourceCreate(platform="manual"))
    session.commit()
    assert len(svc.get_job(session, job.id).sources) == 2


def test_find_job_by_source(session: Session) -> None:
    job = _job(session)
    assert svc.find_job_by_source(session, "rocketpunch", "123").id == job.id
    assert svc.find_job_by_source(session, "rocketpunch", "nope") is None


@pytest.mark.parametrize(
    ("deadline_type", "deadline_date"),
    [(DeadlineType.DATE, None), (DeadlineType.ROLLING, date(2026, 12, 31))],
)
def test_deadline_type_and_date_must_agree(
    session: Session, deadline_type: DeadlineType, deadline_date: date | None
) -> None:
    with pytest.raises(ValidationError):
        _job(session, deadline_type=deadline_type, deadline_date=deadline_date)


def test_deadline_check_constraint_in_db(session: Session) -> None:
    session.add(Job(company_name="a", title="b", deadline_type=DeadlineType.DATE))
    with pytest.raises(IntegrityError):
        session.flush()


def test_update_job_partial_fields_and_status(session: Session) -> None:
    job = _job(session)
    before = job.updated_at
    svc.update_job(
        session,
        job.id,
        JobUpdate(
            status=JobStatus.OPEN,
            deadline_type=DeadlineType.DATE,
            deadline_date=date(2026, 12, 15),
        ),
    )
    session.commit()
    job = svc.get_job(session, job.id)
    assert job.status == JobStatus.OPEN
    assert job.deadline_date == date(2026, 12, 15)
    assert job.title == "AI Agent Engineer (신입)"
    assert job.updated_at >= before


def test_switching_deadline_type_away_from_date_clears_date(session: Session) -> None:
    job = _job(session, deadline_type=DeadlineType.DATE, deadline_date=date(2026, 12, 1))
    svc.update_job(session, job.id, JobUpdate(deadline_type=DeadlineType.UNTIL_FILLED))
    assert job.deadline_date is None


def test_update_rejects_null_for_required_field(session: Session) -> None:
    job = _job(session)
    with pytest.raises(ValidationError):
        svc.update_job(session, job.id, JobUpdate(title=None))


def test_list_jobs_filters(session: Session) -> None:
    _job(session)
    _job(
        session,
        company_name="글로벌세일즈",
        title="해외영업 인턴",
        employment_type=EmploymentType.CONVERSION_INTERN,
        source={"platform": "rocketpunch", "external_id": "456"},
    )
    assert [j.title for j in svc.list_jobs(session, JobFilter(q="해외영업"))] == ["해외영업 인턴"]
    assert (
        len(svc.list_jobs(session, JobFilter(employment_type=EmploymentType.CONVERSION_INTERN)))
        == 1
    )
    assert len(svc.list_jobs(session, JobFilter(seen_since=utcnow() + timedelta(days=1)))) == 0
    assert len(svc.list_jobs(session, JobFilter(limit=1))) == 1


def test_snapshot_is_hashed_and_idempotent(session: Session) -> None:
    job = _job(session)
    source_id = job.sources[0].id
    snap, created = svc.add_snapshot(
        session, job.id, SnapshotCreate(content="자격요건: Python", source_id=source_id)
    )
    assert created
    assert snap.content_hash == svc.content_hash("자격요건: Python")
    again, created_again = svc.add_snapshot(
        session, job.id, SnapshotCreate(content="자격요건: Python")
    )
    assert not created_again
    assert again.id == snap.id
    _, created_new = svc.add_snapshot(session, job.id, SnapshotCreate(content="자격요건: Go"))
    assert created_new
    session.commit()
    assert len(svc.list_snapshots(session, job.id)) == 2


def test_snapshot_rows_cannot_be_updated(session: Session) -> None:
    job = _job(session)
    snap, _ = svc.add_snapshot(session, job.id, SnapshotCreate(content="원문"))
    session.commit()
    snap.content = "변조"
    with pytest.raises(IntegrityError, match="immutable"):
        session.commit()


def test_snapshot_source_must_belong_to_job(session: Session) -> None:
    job_a = _job(session)
    job_b = _job(session, source={"platform": "rocketpunch", "external_id": "999"})
    with pytest.raises(ValidationError):
        svc.add_snapshot(
            session, job_a.id, SnapshotCreate(content="x", source_id=job_b.sources[0].id)
        )


def test_mark_detail_verified_requires_snapshot(session: Session) -> None:
    job = _job(session)
    with pytest.raises(ValidationError):
        svc.mark_detail_verified(session, job.id)
    svc.add_snapshot(session, job.id, SnapshotCreate(content="상세 JD"))
    assert svc.mark_detail_verified(session, job.id).detail_status == DetailStatus.DETAIL_VERIFIED


def test_deleting_job_removes_sources_and_snapshots(session: Session) -> None:
    job = _job(session)
    svc.add_snapshot(session, job.id, SnapshotCreate(content="x", source_id=job.sources[0].id))
    session.commit()
    session.delete(job)
    session.commit()
    assert session.scalars(select(JobSnapshot)).all() == []
