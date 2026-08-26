from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core import database


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_get_db_closes_request_scoped_session(monkeypatch) -> None:
    fake_session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: fake_session)

    dependency: Generator[Session, None, None] = database.get_db()
    assert next(dependency) is fake_session

    try:
        next(dependency)
    except StopIteration:
        pass

    assert fake_session.closed is True
