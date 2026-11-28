"""Job endpoints. Manual registration here is the fallback path (D-010)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from proofit.api.deps import SessionDep
from proofit.schemas.jobs import (
    JobCreate,
    JobDetailRead,
    JobFilter,
    JobRead,
    JobSourceCreate,
    JobSourceRead,
    JobUpdate,
    SnapshotCreate,
    SnapshotRead,
)
from proofit.services import jobs as svc

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(session: SessionDep, flt: Annotated[JobFilter, Query()]):
    return svc.list_jobs(session, flt)


@router.post("", response_model=JobDetailRead, status_code=status.HTTP_201_CREATED)
def create_job(session: SessionDep, data: JobCreate):
    job = svc.create_job(session, data)
    session.commit()
    return job


@router.get("/{job_id}", response_model=JobDetailRead)
def get_job(session: SessionDep, job_id: int):
    return svc.get_job(session, job_id)


@router.patch("/{job_id}", response_model=JobDetailRead)
def update_job(session: SessionDep, job_id: int, data: JobUpdate):
    job = svc.update_job(session, job_id, data)
    session.commit()
    return job


@router.get("/{job_id}/sources", response_model=list[JobSourceRead])
def list_sources(session: SessionDep, job_id: int):
    return svc.get_job(session, job_id).sources


@router.post("/{job_id}/sources", response_model=JobSourceRead, status_code=status.HTTP_201_CREATED)
def add_source(session: SessionDep, job_id: int, data: JobSourceCreate):
    source = svc.add_source(session, job_id, data)
    session.commit()
    return source


@router.get("/{job_id}/snapshots", response_model=list[SnapshotRead])
def list_snapshots(session: SessionDep, job_id: int):
    return svc.list_snapshots(session, job_id)


@router.post("/{job_id}/snapshots", response_model=SnapshotRead)
def add_snapshot(session: SessionDep, job_id: int, data: SnapshotCreate, response: Response):
    """201 when the JD text is new for this job, 200 when an identical snapshot exists."""
    snapshot, created = svc.add_snapshot(session, job_id, data)
    session.commit()
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return snapshot
