from fastapi import APIRouter, UploadFile, status

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile) -> dict[str, str]:
    return {
        "id": "not-implemented",
        "originalName": file.filename or "unnamed",
        "status": "UPLOADED",
    }


@router.post("/{document_id}/analyze")
def analyze_document(document_id: str) -> dict[str, str]:
    return {"documentId": document_id, "status": "PROCESSING"}


@router.put("/{document_id}/confirm")
def confirm_document(document_id: str) -> dict[str, str]:
    return {"documentId": document_id, "status": "CONFIRMED"}
