from sqlalchemy.orm import Session

from app.domains.documents.models import Document


class DocumentRepository:
    def create(self, db: Session, document: Document) -> Document:
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
