from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from proofit.enums import ApplicationStatus as S
from proofit.enums import JobStatus
from proofit.errors import ConflictError, InvalidTransitionError, NotFoundError, ValidationError
from proofit.models.application import Application
from proofit.schemas.applications import ApplicationCreate, ApplicationUpdate, StatusChange
from proofit.schemas.jobs import JobCreate, JobUpdate
from proofit.services import applications as svc
from proofit.services import jobs as job_svc


@pytest.fixture
def job_id(session: Session) -> int:
    job = job_svc.create_job(session, JobCreate(company_name="예시랩스", title="기술영업 신입"))
    session.commit()
    return job.id


def _app(session: Session, job_id: int, status: S = S.REVIEWING) -> Application:
    app = svc.create_application(session, ApplicationCreate(job_id=job_id, status=status))
    session.commit()
    return app


def _move(session: Session, app: Application, *path: S) -> None:
    for status in path:
        svc.change_status(session, app.id, StatusChange(to_status=status))
    session.commit()


def test_create_application_records_initial_event(session: Session, job_id: int) -> None:
    app = _app(session, job_id)
    events = svc.list_events(session, app.id)
    assert [(e.from_status, e.to_status) for e in events] == [(None, S.REVIEWING)]
    assert app.applied_at is None


def test_one_application_per_job(session: Session, job_id: int) -> None:
    _app(session, job_id)
    with pytest.raises(ConflictError):
        _app(session, job_id)


def test_application_for_missing_job(session: Session) -> None:
    with pytest.raises(NotFoundError):
        _app(session, 999)


def test_full_happy_path_records_every_transition(session: Session, job_id: int) -> None:
    app = _app(session, job_id)
    _move(session, app, S.PLANNED, S.APPLIED, S.ASSESSMENT, S.INTERVIEW, S.OFFER)
    events = svc.list_events(session, app.id)
    assert [(e.from_status, e.to_status) for e in events] == [
        (None, S.REVIEWING),
        (S.REVIEWING, S.PLANNED),
        (S.PLANNED, S.APPLIED),
        (S.APPLIED, S.ASSESSMENT),
        (S.ASSESSMENT, S.INTERVIEW),
        (S.INTERVIEW, S.OFFER),
    ]
    assert not any(e.is_correction for e in events)
    assert svc.get_application(session, app.id).status == S.OFFER


def test_applied_at_set_once_from_occurred_at(session: Session, job_id: int) -> None:
    app = _app(session, job_id)
    when = datetime(2026, 11, 20, 1, 0, tzinfo=UTC)
    svc.change_status(session, app.id, StatusChange(to_status=S.APPLIED, occurred_at=when))
    _move(session, app, S.INTERVIEW)
    assert svc.get_application(session, app.id).applied_at == when


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ((), S.OFFER),  # 검토 → 합격: 지원하지 않은 공고는 합격할 수 없음
        ((S.APPLIED,), S.SKIPPED),  # 지원 후 건너뜀 불가 → 철회 사용
        ((S.APPLIED,), S.PLANNED),  # 뒤로 이동
        ((S.SKIPPED,), S.PLANNED),  # 종료 상태에서 재개
        ((S.APPLIED, S.REJECTED), S.INTERVIEW),
    ],
)
def test_disallowed_transitions_are_rejected(
    session: Session, job_id: int, path: tuple[S, ...], target: S
) -> None:
    app = _app(session, job_id)
    _move(session, app, *path)
    before = len(svc.list_events(session, app.id))
    with pytest.raises(InvalidTransitionError, match="정정"):
        svc.change_status(session, app.id, StatusChange(to_status=target))
    session.rollback()
    assert len(svc.list_events(session, app.id)) == before


def test_same_status_is_rejected(session: Session, job_id: int) -> None:
    app = _app(session, job_id)
    with pytest.raises(InvalidTransitionError, match="이미"):
        svc.change_status(session, app.id, StatusChange(to_status=S.REVIEWING))


def test_assessment_and_interview_may_alternate(session: Session, job_id: int) -> None:
    app = _app(session, job_id, status=S.APPLIED)
    _move(session, app, S.INTERVIEW, S.ASSESSMENT, S.INTERVIEW, S.REJECTED)
    assert app.status == S.REJECTED


def test_declining_offer_is_withdrawn(session: Session, job_id: int) -> None:
    app = _app(session, job_id, status=S.APPLIED)
    _move(session, app, S.OFFER, S.WITHDRAWN)
    assert app.status == S.WITHDRAWN


def test_correction_requires_note_and_is_flagged(session: Session, job_id: int) -> None:
    app = _app(session, job_id)
    _move(session, app, S.SKIPPED)
    with pytest.raises(ValidationError, match="사유"):
        svc.change_status(session, app.id, StatusChange(to_status=S.REVIEWING, correction=True))
    svc.change_status(
        session,
        app.id,
        StatusChange(to_status=S.REVIEWING, correction=True, note="실수로 건너뜀 처리"),
    )
    session.commit()
    last = svc.list_events(session, app.id)[-1]
    assert (last.from_status, last.to_status, last.is_correction) == (
        S.SKIPPED,
        S.REVIEWING,
        True,
    )


def test_correction_flag_on_allowed_transition_is_not_marked(session: Session, job_id: int) -> None:
    app = _app(session, job_id)
    svc.change_status(
        session, app.id, StatusChange(to_status=S.PLANNED, correction=True, note="메모")
    )
    assert svc.list_events(session, app.id)[-1].is_correction is False


def test_events_are_immutable(session: Session, job_id: int) -> None:
    app = _app(session, job_id)
    event = svc.list_events(session, app.id)[0]
    event.note = "변조"
    with pytest.raises(IntegrityError, match="immutable"):
        session.commit()


def test_job_status_and_application_status_are_independent(session: Session, job_id: int) -> None:
    app = _app(session, job_id, status=S.APPLIED)
    job_svc.update_job(session, job_id, JobUpdate(status=JobStatus.CLOSED))
    session.commit()
    assert svc.get_application(session, app.id).status == S.APPLIED
    _move(session, app, S.INTERVIEW)
    assert job_svc.get_job(session, job_id).status == JobStatus.CLOSED


def test_list_applications_by_status_and_update_note(session: Session, job_id: int) -> None:
    app = _app(session, job_id)
    svc.update_application(session, app.id, ApplicationUpdate(note="채용설명회 확인"))
    session.commit()
    assert [a.id for a in svc.list_applications(session, S.REVIEWING)] == [app.id]
    assert svc.list_applications(session, S.APPLIED) == []
    assert svc.get_application(session, app.id).note == "채용설명회 확인"


def test_every_status_has_transition_rules_and_label() -> None:
    assert set(svc.ALLOWED_TRANSITIONS) == set(S)
    assert set(svc.STATUS_LABELS_KO) == set(S)
    for terminal in svc.TERMINAL_STATUSES - {S.OFFER}:
        assert svc.ALLOWED_TRANSITIONS[terminal] == frozenset()
