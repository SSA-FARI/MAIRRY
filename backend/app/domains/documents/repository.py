from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.documents.models import Document


class DocumentRepository:
    def create(self, db: Session, document: Document) -> Document:
        db.add(document)
        return document

    def get_by_id(
        self,
        db: Session,
        document_id: UUID,
        wedding_plan_id: UUID,
        *,
        for_update: bool = False,
    ) -> Document | None:
        query = db.query(Document).filter(
            Document.id == document_id, Document.wedding_plan_id == wedding_plan_id
        )
        if for_update:
            query = query.with_for_update()
        return query.one_or_none()
