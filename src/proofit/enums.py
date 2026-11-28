"""Domain enums. Values are stable English identifiers; Korean labels are for display."""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    OPEN = "OPEN"  # 공고 진행
    CLOSED = "CLOSED"  # 마감
    UNKNOWN = "UNKNOWN"  # 미확인


class DetailStatus(StrEnum):
    LISTING_ONLY = "LISTING_ONLY"  # 목록 메타데이터만 있음 (예: 알림 메일)
    DETAIL_VERIFIED = "DETAIL_VERIFIED"  # 검증된 상세 JD 확보


class EmploymentType(StrEnum):
    FULL_TIME = "FULL_TIME"  # 정규직
    CONTRACT = "CONTRACT"  # 계약직
    INTERN = "INTERN"  # 인턴
    CONVERSION_INTERN = "CONVERSION_INTERN"  # 채용연계형 인턴
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class ExperienceLevel(StrEnum):
    NEW_GRAD = "NEW_GRAD"  # 신입
    ANY = "ANY"  # 경력무관
    NEW_OR_EXPERIENCED = "NEW_OR_EXPERIENCED"  # 신입·경력
    EXPERIENCED = "EXPERIENCED"  # 경력
    UNKNOWN = "UNKNOWN"


class DeadlineType(StrEnum):
    DATE = "DATE"  # 마감일 지정
    ROLLING = "ROLLING"  # 상시채용
    UNTIL_FILLED = "UNTIL_FILLED"  # 채용 시 마감
    UNKNOWN = "UNKNOWN"


class WorkMode(StrEnum):
    ONSITE = "ONSITE"
    HYBRID = "HYBRID"
    REMOTE = "REMOTE"
    UNKNOWN = "UNKNOWN"


class ApplicationStatus(StrEnum):
    REVIEWING = "REVIEWING"  # 검토
    PLANNED = "PLANNED"  # 지원 예정
    APPLIED = "APPLIED"  # 지원
    ASSESSMENT = "ASSESSMENT"  # 시험
    INTERVIEW = "INTERVIEW"  # 면접
    OFFER = "OFFER"  # 합격
    REJECTED = "REJECTED"  # 불합격
    WITHDRAWN = "WITHDRAWN"  # 철회
    SKIPPED = "SKIPPED"  # 건너뜀


class EvidenceKind(StrEnum):
    EDUCATION = "EDUCATION"
    EXPERIENCE = "EXPERIENCE"
    PROJECT = "PROJECT"
    PAPER = "PAPER"
    GLOBAL_EXPERIENCE = "GLOBAL_EXPERIENCE"
    CERTIFICATION = "CERTIFICATION"
    SKILL = "SKILL"
    OTHER = "OTHER"


class ReviewStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
