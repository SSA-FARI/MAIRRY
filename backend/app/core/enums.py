from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"
    CONFIRMED = "CONFIRMED"


class DocumentType(StrEnum):
    WEDDING_HALL = "WEDDING_HALL"
    UNKNOWN = "UNKNOWN"


class AnalysisSource(StrEnum):
    LIVE_AI = "LIVE_AI"
    DEMO_FALLBACK = "DEMO_FALLBACK"


class ContractStatus(StrEnum):
    CONFIRMED = "CONFIRMED"


class PaymentStatus(StrEnum):
    PAID = "PAID"
    UNPAID = "UNPAID"
    UNKNOWN = "UNKNOWN"


class WeddingPlanStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class WeddingPlanMemberRole(StrEnum):
    OWNER = "OWNER"
    PARTNER = "PARTNER"


class AssetOwnerType(StrEnum):
    PERSONAL = "PERSONAL"
    JOINT = "JOINT"


class AssetCategory(StrEnum):
    CASH = "CASH"
    SAVINGS = "SAVINGS"


class AnswerType(StrEnum):
    CONTRACT = "CONTRACT"
    CALCULATION = "CALCULATION"
    NOT_FOUND = "NOT_FOUND"
