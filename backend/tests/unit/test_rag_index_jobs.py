from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from ai.rag.embeddings import EmbeddingError
from app.core.enums import ContractStatus, DocumentType
from app.domains.contracts.models import Contract
from app.domains.rag.models import RagIndexJob, RagIndexJobStatus
from app.domains.rag.repository import RagRepository
from app.domains.rag.service import process_next_index_job


class TrackingSession:
    def __init__(self, scalar_result=None, *, scalar_error: Exception | None = None) -> None:
        self.scalar_result = scalar_result
        self.scalar_error = scalar_error
        self.statement = None
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def scalar(self, statement):
        self.statement = statement
        if self.scalar_error is not None:
            raise self.scalar_error
        return self.scalar_result

    def get(self, _model, _identifier):
        return None

    def flush(self) -> None:
        pass

    def execute(self, _statement):
        return None

    def add_all(self, _items) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class SessionQueue:
    def __init__(self, *sessions: TrackingSession) -> None:
        self.sessions = list(sessions)

    def __call__(self):
        return self.sessions.pop(0)


class ObservingEmbedder:
    model_name = "text-embedding-3-small"
    version = "v1"
    dimensions = 1536

    def __init__(self, prior_sessions: list[TrackingSession], *, fail: bool = False) -> None:
        self.prior_sessions = prior_sessions
        self.fail = fail
        self.called = False

    def embed_many(self, texts):
        self.called = True
        assert all(session.closed for session in self.prior_sessions)
        if self.fail:
            raise EmbeddingError("provider unavailable")
        return [[1.0] + [0.0] * 1535 for _ in texts]


def _configuration() -> SimpleNamespace:
    return SimpleNamespace(
        rag_index_stale_after_seconds=300,
        rag_index_max_attempts=3,
        rag_index_retry_base_seconds=5,
        rag_chunk_size=900,
        rag_chunk_overlap=120,
    )


def _job(contract_id: UUID) -> RagIndexJob:
    return RagIndexJob(
        id=UUID(int=2),
        contract_id=contract_id,
        document_version=1,
        status=RagIndexJobStatus.PENDING.value,
        attempts=0,
    )


def _contract(contract_id: UUID) -> Contract:
    contract = Contract(
        id=contract_id,
        wedding_plan_id=UUID(int=10),
        document_id=UUID(int=11),
        document_type=DocumentType.WEDDING_HALL,
        company="테스트 웨딩홀",
        total_price=1_000_000,
        status=ContractStatus.CONFIRMED,
    )
    contract.payments = []
    contract.cancellation_terms = []
    return contract


def test_claim_uses_skip_locked_and_recovers_only_eligible_jobs() -> None:
    session = TrackingSession()
    now = datetime(2026, 9, 8, tzinfo=UTC)

    result = RagRepository(session).claim_retryable_job(  # type: ignore[arg-type]
        now=now,
        stale_before=now - timedelta(minutes=5),
        max_attempts=3,
    )

    compiled = session.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert result is None
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "rag_index_jobs.attempts" in sql
    assert "rag_index_jobs.next_attempt_at" in sql
    assert "rag_index_jobs.locked_at" in sql


def test_embedding_runs_after_claim_and_read_sessions_are_closed() -> None:
    contract_id = UUID(int=1)
    job = _job(contract_id)
    claim_session = TrackingSession(job)
    read_session = TrackingSession(_contract(contract_id))
    complete_session = TrackingSession(job)
    embedder = ObservingEmbedder([claim_session, read_session])

    processed = process_next_index_job(
        _configuration(),  # type: ignore[arg-type]
        session_factory=SessionQueue(claim_session, read_session, complete_session),
        embedding_client=embedder,
        now_factory=lambda: datetime(2026, 9, 8, tzinfo=UTC),
    )

    assert processed is True
    assert embedder.called is True
    assert claim_session.committed is True
    assert complete_session.committed is True
    assert all(session.closed for session in [claim_session, read_session, complete_session])
    assert job.status == RagIndexJobStatus.INDEXED.value
    assert job.attempts == 1
    assert job.locked_at is None


def test_embedding_failure_is_recorded_with_a_new_session_and_backoff() -> None:
    contract_id = UUID(int=1)
    job = _job(contract_id)
    claim_session = TrackingSession(job)
    read_session = TrackingSession(_contract(contract_id))
    failure_session = TrackingSession(job)
    embedder = ObservingEmbedder([claim_session, read_session], fail=True)
    now = datetime(2026, 9, 8, tzinfo=UTC)

    processed = process_next_index_job(
        _configuration(),  # type: ignore[arg-type]
        session_factory=SessionQueue(claim_session, read_session, failure_session),
        embedding_client=embedder,
        now_factory=lambda: now,
    )

    assert processed is True
    assert claim_session.committed is True
    assert failure_session.committed is True
    assert all(session.closed for session in [claim_session, read_session, failure_session])
    assert job.status == RagIndexJobStatus.FAILED.value
    assert job.error_code == "EMBEDDING_ERROR"
    assert job.attempts == 1
    assert job.next_attempt_at == now + timedelta(seconds=5)


def test_failure_recording_database_outage_leaves_a_stale_recoverable_lease() -> None:
    contract_id = UUID(int=1)
    job = _job(contract_id)
    claim_session = TrackingSession(job)
    read_session = TrackingSession(_contract(contract_id))
    failed_record_session = TrackingSession(scalar_error=SQLAlchemyError("database down"))
    embedder = ObservingEmbedder([claim_session, read_session], fail=True)
    now = datetime(2026, 9, 8, tzinfo=UTC)

    processed = process_next_index_job(
        _configuration(),  # type: ignore[arg-type]
        session_factory=SessionQueue(claim_session, read_session, failed_record_session),
        embedding_client=embedder,
        now_factory=lambda: now,
    )

    assert processed is True
    assert failed_record_session.rolled_back is True
    assert failed_record_session.closed is True
    assert job.status == RagIndexJobStatus.INDEXING.value
    assert job.locked_at == now
    assert job.attempts == 1
