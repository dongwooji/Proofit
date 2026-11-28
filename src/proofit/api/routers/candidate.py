"""Profile, project, and evidence endpoints. PATCH on evidence appends a new version."""

from __future__ import annotations

from fastapi import APIRouter, status

from proofit.api.deps import SessionDep
from proofit.schemas.candidate import (
    EvidenceCreate,
    EvidenceRead,
    EvidenceUpdate,
    EvidenceVersionRead,
    ProfileRead,
    ProfileUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)
from proofit.services import evidence as svc

router = APIRouter(prefix="/api", tags=["candidate"])


@router.get("/profile", response_model=ProfileRead)
def get_profile(session: SessionDep):
    profile = svc.get_or_create_profile(session)
    session.commit()
    return profile


@router.put("/profile", response_model=ProfileRead)
def update_profile(session: SessionDep, data: ProfileUpdate):
    profile = svc.update_profile(session, data)
    session.commit()
    return profile


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(session: SessionDep):
    projects = svc.list_projects(session)
    session.commit()  # may have created the profile
    return projects


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(session: SessionDep, data: ProjectCreate):
    project = svc.create_project(session, data)
    session.commit()
    return project


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(session: SessionDep, project_id: int):
    return svc.get_project(session, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(session: SessionDep, project_id: int, data: ProjectUpdate):
    project = svc.update_project(session, project_id, data)
    session.commit()
    return project


@router.get("/evidence", response_model=list[EvidenceRead])
def list_evidence(session: SessionDep, project_id: int | None = None):
    return svc.list_evidence(session, project_id)


@router.post("/evidence", response_model=EvidenceRead, status_code=status.HTTP_201_CREATED)
def create_evidence(session: SessionDep, data: EvidenceCreate):
    item = svc.create_evidence(session, data)
    session.commit()
    return item


@router.get("/evidence/{item_id}", response_model=EvidenceRead)
def get_evidence(session: SessionDep, item_id: int):
    return svc.get_evidence(session, item_id)


@router.patch(
    "/evidence/{item_id}",
    response_model=EvidenceVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def update_evidence(session: SessionDep, item_id: int, data: EvidenceUpdate):
    version = svc.update_evidence(session, item_id, data)
    session.commit()
    return version


@router.get("/evidence/{item_id}/versions", response_model=list[EvidenceVersionRead])
def list_versions(session: SessionDep, item_id: int):
    return svc.list_versions(session, item_id)


@router.post("/evidence-versions/{version_id}/confirm", response_model=EvidenceVersionRead)
def confirm_version(session: SessionDep, version_id: int):
    version = svc.confirm_version(session, version_id)
    session.commit()
    return version
