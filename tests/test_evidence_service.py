import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from proofit.enums import EvidenceKind, EvidenceOrigin, ReviewStatus
from proofit.errors import ConflictError, NotFoundError, ValidationError
from proofit.models.candidate import EvidenceItem
from proofit.schemas.candidate import (
    EvidenceCreate,
    EvidenceUpdate,
    ProfileUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from proofit.services import evidence as svc

SHA = "0123456789abcdef0123456789abcdef01234567"


def _evidence(session: Session, **overrides) -> EvidenceItem:
    data = {
        "kind": EvidenceKind.PROJECT,
        "claim": "BM25 + Dense 하이브리드 검색 파이프라인 설계·구현",
        "skills": ["Python", "LangGraph"],
        "metric": "Hybrid Recall@10 0.62 → 0.81",
    }
    data.update(overrides)
    item = svc.create_evidence(session, EvidenceCreate.model_validate(data))
    session.commit()
    return item


def test_profile_is_single_and_updatable(session: Session) -> None:
    first = svc.get_or_create_profile(session)
    assert svc.get_or_create_profile(session).id == first.id
    svc.update_profile(session, ProfileUpdate(display_name="홍길동"))
    session.commit()
    assert svc.get_or_create_profile(session).display_name == "홍길동"


def test_project_crud_and_period_validation(session: Session) -> None:
    project = svc.create_project(
        session,
        ProjectCreate(title="Agentic RAG", my_role="검색 파이프라인 담당", period_start="2025-03"),
    )
    session.commit()
    svc.update_project(session, project.id, ProjectUpdate(period_end="2025-08"))
    assert svc.get_project(session, project.id).period_end == "2025-08"
    assert [p.id for p in svc.list_projects(session)] == [project.id]
    with pytest.raises(ValidationError, match="종료 시기"):
        svc.update_project(session, project.id, ProjectUpdate(period_end="2024-01"))
    with pytest.raises(ValidationError):
        svc.update_project(session, project.id, ProjectUpdate(title=None))


def test_create_evidence_makes_first_draft_version(session: Session) -> None:
    item = _evidence(session)
    version = item.current_version
    assert version.version_no == 1
    assert version.review_status == ReviewStatus.DRAFT
    assert version.confirmed_at is None
    assert version.skills == ["Python", "LangGraph"]


def test_evidence_linked_to_missing_project_is_rejected(session: Session) -> None:
    with pytest.raises(NotFoundError):
        _evidence(session, project_id=999)


def test_skills_are_trimmed_and_deduplicated(session: Session) -> None:
    item = _evidence(session, skills=[" Python", "Python", "", "SQL "])
    assert item.current_version.skills == ["Python", "SQL"]


def test_update_appends_version_and_keeps_old_one(session: Session) -> None:
    item = _evidence(session, confirm=True)
    v1_id = item.current_version.id
    v2 = svc.update_evidence(session, item.id, EvidenceUpdate(metric="Recall@10 0.62 → 0.83"))
    session.commit()
    versions = svc.list_versions(session, item.id)
    assert [v.version_no for v in versions] == [1, 2]
    v1 = svc.get_version(session, v1_id)
    assert v1.metric == "Hybrid Recall@10 0.62 → 0.81"
    assert v1.review_status == ReviewStatus.CONFIRMED
    assert v2.metric == "Recall@10 0.62 → 0.83"
    assert v2.claim == v1.claim  # unchanged fields are carried over
    assert v2.review_status == ReviewStatus.DRAFT
    assert svc.get_evidence(session, item.id).current_version.id == v2.id


def test_update_without_changes_is_rejected(session: Session) -> None:
    item = _evidence(session)
    with pytest.raises(ValidationError, match="변경된 내용"):
        svc.update_evidence(session, item.id, EvidenceUpdate(skills=["Python", "LangGraph"]))


def test_confirm_is_one_way(session: Session) -> None:
    item = _evidence(session)
    version = svc.confirm_version(session, item.current_version.id)
    session.commit()
    assert version.review_status == ReviewStatus.CONFIRMED
    assert version.confirmed_at is not None
    with pytest.raises(ConflictError):
        svc.confirm_version(session, version.id)


def test_ai_drafts_cannot_be_confirmed_on_creation(session: Session) -> None:
    with pytest.raises(ValidationError, match="AI"):
        _evidence(
            session,
            origin=EvidenceOrigin.RESUME,
            confirm=True,
        )


def test_github_evidence_requires_url_and_commit_sha(session: Session) -> None:
    with pytest.raises(ValidationError, match="커밋 SHA"):
        _evidence(session, origin=EvidenceOrigin.GITHUB, source_url="https://github.com/x/y")
    item = _evidence(
        session,
        origin=EvidenceOrigin.GITHUB,
        source_url="https://github.com/x/y",
        commit_sha=SHA,
    )
    assert item.current_version.commit_sha == SHA


def test_invalid_commit_sha_is_rejected_by_schema() -> None:
    with pytest.raises(ValueError):
        EvidenceCreate(kind=EvidenceKind.PROJECT, claim="x", commit_sha="not-a-sha")


def test_version_content_is_immutable_in_db(session: Session) -> None:
    item = _evidence(session)
    item.current_version.claim = "부풀린 주장"
    with pytest.raises(IntegrityError, match="immutable"):
        session.commit()


def test_confirmed_version_cannot_be_reverted_in_db(session: Session) -> None:
    item = _evidence(session, confirm=True)
    with pytest.raises(IntegrityError, match="DRAFT -> CONFIRMED"):
        session.execute(
            text("UPDATE evidence_item_versions SET review_status = 'DRAFT' WHERE id = :id"),
            {"id": item.current_version.id},
        )


def test_only_confirmed_evidence_is_listed_for_evaluation(session: Session) -> None:
    confirmed = _evidence(session, confirm=True)
    _evidence(session, claim="아직 확인 안 한 초안")
    # A newer draft on a confirmed item does not hide the confirmed version.
    svc.update_evidence(session, confirmed.id, EvidenceUpdate(claim="수정 중인 초안"))
    session.commit()
    usable = svc.list_confirmed_evidence(session)
    assert [(v.item_id, v.version_no) for v in usable] == [(confirmed.id, 1)]


def test_list_evidence_by_project(session: Session) -> None:
    project = svc.create_project(session, ProjectCreate(title="논문"))
    in_project = _evidence(session, project_id=project.id)
    _evidence(session)
    assert [e.id for e in svc.list_evidence(session, project_id=project.id)] == [in_project.id]
