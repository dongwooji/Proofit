from __future__ import annotations

from fastapi import APIRouter, status

from proofit.api.deps import SessionDep
from proofit.enums import ApplicationStatus
from proofit.schemas.applications import (
    ApplicationCreate,
    ApplicationEventRead,
    ApplicationRead,
    ApplicationUpdate,
    StatusChange,
)
from proofit.services import applications as svc

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationRead])
def list_applications(session: SessionDep, status: ApplicationStatus | None = None):
    return svc.list_applications(session, status)


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(session: SessionDep, data: ApplicationCreate):
    app = svc.create_application(session, data)
    session.commit()
    return app


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(session: SessionDep, application_id: int):
    return svc.get_application(session, application_id)


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(session: SessionDep, application_id: int, data: ApplicationUpdate):
    app = svc.update_application(session, application_id, data)
    session.commit()
    return app


@router.patch("/{application_id}/status", response_model=ApplicationRead)
def change_status(session: SessionDep, application_id: int, data: StatusChange):
    app = svc.change_status(session, application_id, data)
    session.commit()
    return app


@router.get("/{application_id}/events", response_model=list[ApplicationEventRead])
def list_events(session: SessionDep, application_id: int):
    return svc.list_events(session, application_id)
