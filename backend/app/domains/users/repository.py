from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domains.users.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._session.get(User, user_id)

    def insert_demo_if_absent(
        self,
        *,
        user_id: UUID,
        login_id: str,
        password_hash: str,
        display_name: str,
        email: str | None,
    ) -> None:
        statement = (
            insert(User)
            .values(
                id=user_id,
                login_id=login_id,
                password_hash=password_hash,
                display_name=display_name,
                email=email,
            )
            .on_conflict_do_nothing()
        )
        self._session.execute(statement)
