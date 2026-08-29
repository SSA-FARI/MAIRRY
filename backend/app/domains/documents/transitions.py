from fastapi import status

from app.core.enums import DocumentStatus
from app.core.error_codes import ErrorCode
from app.core.errors import AppError

ALLOWED_TRANSITIONS: dict[DocumentStatus, frozenset[DocumentStatus]] = {
    DocumentStatus.UPLOADED: frozenset({DocumentStatus.PROCESSING}),
    DocumentStatus.PROCESSING: frozenset({DocumentStatus.REVIEW_REQUIRED, DocumentStatus.FAILED}),
    DocumentStatus.REVIEW_REQUIRED: frozenset({DocumentStatus.CONFIRMED}),
    DocumentStatus.FAILED: frozenset({DocumentStatus.PROCESSING, DocumentStatus.CONFIRMED}),
    DocumentStatus.CONFIRMED: frozenset(),
}


def ensure_transition_allowed(current: DocumentStatus, target: DocumentStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise AppError(
            code=ErrorCode.INVALID_STATE,
            message=f"{current.value} 상태에서 {target.value}(으)로 전이할 수 없습니다.",
            status_code=status.HTTP_409_CONFLICT,
        )
