from ai.document_extraction.schemas import DocumentExtraction


def requires_user_review(extraction: DocumentExtraction) -> bool:
    if extraction.company is None or extraction.total_price is None:
        return True
    return bool(extraction.warnings)
