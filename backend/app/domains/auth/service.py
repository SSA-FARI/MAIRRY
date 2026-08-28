import logging

from fastapi import status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.error_codes import ErrorCode
from app.core.errors import AppError
from app.domains.auth.passwords import create_unusable_demo_password_hash
from app.domains.auth.schemas import DemoLoginResponse, DemoUserRead
from app.domains.users.models import User
from app.domains.users.repository import UserRepository

logger = logging.getLogger(__name__)


class DemoLoginService:
    def __init__(self, session: Session, configuration: Settings) -> None:
        self._session = session
        self._configuration = configuration
        self._users = UserRepository(session)

    def login(self) -> DemoLoginResponse:
        existing_user = self._users.get_by_id(self._configuration.demo_user_id)
        if existing_user is not None:
            self._warn_if_profile_differs(existing_user)
            return self._to_response(existing_user)

        try:
            self._users.insert_demo_if_absent(
                user_id=self._configuration.demo_user_id,
                login_id=self._configuration.demo_user_login_id,
                password_hash=create_unusable_demo_password_hash(),
                display_name=self._configuration.demo_user_display_name,
                email=self._configuration.demo_user_email,
            )
            self._session.commit()
        except SQLAlchemyError as exc:
            self._session.rollback()
            raise AppError(
                code=ErrorCode.INTERNAL_ERROR,
                message="Demo User를 준비하지 못했습니다.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        persisted_user = self._users.get_by_id(self._configuration.demo_user_id)
        if persisted_user is None:
            self._session.rollback()
            logger.error("Demo user configuration conflicts with an existing unique user field")
            raise AppError(
                code=ErrorCode.CONFIGURATION_ERROR,
                message="Demo User 설정을 확인해 주세요.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        self._warn_if_profile_differs(persisted_user)
        return self._to_response(persisted_user)

    def _warn_if_profile_differs(self, user: User) -> None:
        configured_profile = {
            "login_id": self._configuration.demo_user_login_id,
            "display_name": self._configuration.demo_user_display_name,
            "email": self._configuration.demo_user_email,
        }
        mismatched_fields = [
            field_name
            for field_name, configured_value in configured_profile.items()
            if getattr(user, field_name) != configured_value
        ]
        if mismatched_fields:
            logger.warning(
                "Persisted demo user profile differs from configuration; using database values "
                "(fields=%s)",
                ",".join(mismatched_fields),
            )

    @staticmethod
    def _to_response(user: User) -> DemoLoginResponse:
        return DemoLoginResponse(
            user=DemoUserRead(
                id=user.id,
                login_id=user.login_id,
                display_name=user.display_name,
                email=user.email,
            )
        )
