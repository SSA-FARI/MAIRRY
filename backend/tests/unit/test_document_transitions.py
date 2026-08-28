import pytest

from app.core.enums import DocumentStatus
from app.core.errors import AppError
from app.domains.documents.transitions import ensure_transition_allowed


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (DocumentStatus.UPLOADED, DocumentStatus.PROCESSING),
        (DocumentStatus.PROCESSING, DocumentStatus.REVIEW_REQUIRED),
        (DocumentStatus.PROCESSING, DocumentStatus.FAILED),
        (DocumentStatus.REVIEW_REQUIRED, DocumentStatus.CONFIRMED),
        (DocumentStatus.FAILED, DocumentStatus.PROCESSING),
        (DocumentStatus.FAILED, DocumentStatus.CONFIRMED),
    ],
)
def test_ensure_transition_allowed_accepts_valid_transitions(
    current: DocumentStatus, target: DocumentStatus
) -> None:
    ensure_transition_allowed(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (DocumentStatus.UPLOADED, DocumentStatus.REVIEW_REQUIRED),
        (DocumentStatus.UPLOADED, DocumentStatus.CONFIRMED),
        (DocumentStatus.REVIEW_REQUIRED, DocumentStatus.PROCESSING),
        (DocumentStatus.CONFIRMED, DocumentStatus.PROCESSING),
        (DocumentStatus.CONFIRMED, DocumentStatus.REVIEW_REQUIRED),
    ],
)
def test_ensure_transition_allowed_rejects_invalid_transitions(
    current: DocumentStatus, target: DocumentStatus
) -> None:
    with pytest.raises(AppError) as excinfo:
        ensure_transition_allowed(current, target)

    assert excinfo.value.status_code == 409
    assert excinfo.value.code.value == "INVALID_STATE"
