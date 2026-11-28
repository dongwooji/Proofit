"""ORM models. Import every model module here so `Base.metadata` is complete for Alembic."""

from proofit.db.base import Base
from proofit.models.application import Application, ApplicationEvent
from proofit.models.candidate import CandidateProfile, EvidenceItem, EvidenceItemVersion, Project
from proofit.models.job import Job, JobSnapshot, JobSource

__all__ = [
    "Application",
    "ApplicationEvent",
    "Base",
    "CandidateProfile",
    "EvidenceItem",
    "EvidenceItemVersion",
    "Job",
    "JobSnapshot",
    "JobSource",
    "Project",
]
