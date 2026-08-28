from uuid import UUID

from app.core.enums import DocumentStatus
from app.core.schema import ApiModel


class DocumentUploadResponse(ApiModel):
    id: UUID
    original_name: str
    status: DocumentStatus
