"""Application status tracking with validated transitions and an event log.

Job status (공고 진행/마감) and application status are independent: nothing here
reads or changes `Job.status`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from proofit.db.base import utcnow
from proofit.enums import ApplicationStatus as S
from proofit.errors import ConflictError, InvalidTransitionError, NotFoundError, ValidationError
from proofit.models.application import Application, ApplicationEvent
from proofit.schemas.applications import ApplicationCreate, ApplicationUpdate, StatusChange
from proofit.services.jobs import get_job

STATUS_LABELS_KO: dict[S, str] = {
    S.REVIEWING: "검토",
    S.PLANNED: "지원 예정",
    S.APPLIED: "지원",
    S.ASSESSMENT: "시험",
    S.INTERVIEW: "면접",
    S.OFFER: "합격",
    S.REJECTED: "불합격",
    S.WITHDRAWN: "철회",
    S.SKIPPED: "건너뜀",
}

TERMINAL_STATUSES = frozenset({S.OFFER, S.REJECTED, S.WITHDRAWN, S.SKIPPED})
_SUBMITTED = (S.APPLIED, S.ASSESSMENT, S.INTERVIEW)
_AFTER_SUBMISSION = {S.OFFER, S.REJECTED, S.WITHDRAWN}

# Normal transitions (docs/decisions.md D-038). Anything else needs `correction=True`.
# - Active stages move forward and may skip ahead (e.g. 검토 → 지원).
# - 시험 and 면접 may alternate, since companies order them differently.
# - 건너뜀 only before submitting; 합격/불합격/철회 only after submitting.
# - 합격 → 철회 records declining an offer.
ALLOWED_TRANSITIONS: dict[S, frozenset[S]] = {
    S.REVIEWING: frozenset({S.PLANNED, *_SUBMITTED, S.SKIPPED}),
    S.PLANNED: frozenset({*_SUBMITTED, S.SKIPPED}),
    S.APPLIED: frozenset({S.ASSESSMENT, S.INTERVIEW, *_AFTER_SUBMISSION}),
    S.ASSESSMENT: frozenset({S.INTERVIEW, *_AFTER_SUBMISSION}),
    S.INTERVIEW: frozenset({S.ASSESSMENT, *_AFTER_SUBMISSION}),
    S.OFFER: frozenset({S.WITHDRAWN}),
    S.REJECTED: frozenset(),
    S.WITHDRAWN: frozenset(),
    S.SKIPPED: frozenset(),
}


def is_allowed_transition(from_status: S, to_status: S) -> bool:
    return to_status in ALLOWED_TRANSITIONS[from_status]


def get_application(session: Session, application_id: int) -> Application:
    app = session.get(Application, application_id)
    if app is None:
        raise NotFoundError(f"지원 기록(id={application_id})을 찾을 수 없습니다.")
    return app


def get_application_by_job(session: Session, job_id: int) -> Application | None:
    return session.scalars(select(Application).where(Application.job_id == job_id)).first()


def create_application(session: Session, data: ApplicationCreate) -> Application:
    job = get_job(session, data.job_id)
    if get_application_by_job(session, job.id) is not None:
        raise ConflictError(f"이 공고(id={job.id})에는 이미 지원 기록이 있습니다.")
    now = utcnow()
    app = Application(
        job_id=job.id,
        status=data.status,
        note=data.note,
        applied_at=now if data.status == S.APPLIED else None,
    )
    app.events.append(ApplicationEvent(from_status=None, to_status=data.status, occurred_at=now))
    session.add(app)
    session.flush()
    return app


def change_status(session: Session, application_id: int, change: StatusChange) -> Application:
    app = get_application(session, application_id)
    current, target = app.status, change.to_status
    if current == target:
        raise InvalidTransitionError(f"이미 '{STATUS_LABELS_KO[target]}' 상태입니다.")
    allowed = is_allowed_transition(current, target)
    if not allowed and not change.correction:
        raise InvalidTransitionError(
            f"'{STATUS_LABELS_KO[current]}'에서 '{STATUS_LABELS_KO[target]}'(으)로 바로 바꿀 수 "
            "없습니다. 잘못 기록한 상태를 고치려면 정정(correction)으로 사유를 남겨 주세요."
        )
    if change.correction and not (change.note and change.note.strip()):
        raise ValidationError("상태를 정정할 때는 사유(note)를 입력해야 합니다.")

    occurred_at = change.occurred_at or utcnow()
    app.events.append(
        ApplicationEvent(
            from_status=current,
            to_status=target,
            # Only flag events that actually needed the override.
            is_correction=not allowed,
            note=change.note,
            occurred_at=occurred_at,
        )
    )
    app.status = target
    if target == S.APPLIED and app.applied_at is None:
        app.applied_at = occurred_at
    session.flush()
    return app


def update_application(
    session: Session, application_id: int, data: ApplicationUpdate
) -> Application:
    app = get_application(session, application_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(app, field, value)
    session.flush()
    return app


def list_applications(session: Session, status: S | None = None) -> list[Application]:
    stmt = select(Application).order_by(Application.updated_at.desc(), Application.id.desc())
    if status is not None:
        stmt = stmt.where(Application.status == status)
    return list(session.scalars(stmt))


def list_events(session: Session, application_id: int) -> list[ApplicationEvent]:
    return list(get_application(session, application_id).events)
