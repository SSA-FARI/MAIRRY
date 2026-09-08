from uuid import UUID

from sqlalchemy.dialects import postgresql

from app.core.enums import DocumentType
from app.domains.contracts.repository import ContractRepository


class EmptyScalars:
    def all(self):
        return []


class CapturingSession:
    def __init__(self) -> None:
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return EmptyScalars()


def test_matching_contract_lookup_scopes_plan_status_and_category_in_sql() -> None:
    session = CapturingSession()
    plan_id = UUID(int=41)

    result = ContractRepository(session).list_confirmed_matching(  # type: ignore[arg-type]
        plan_id,
        company_terms=("스튜디오", "드레스", "메이크업"),
        document_types=(DocumentType.WEDDING_HALL,),
    )

    compiled = session.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert result == []
    assert "contracts.wedding_plan_id" in sql
    assert "contracts.status" in sql
    assert "contracts.company ILIKE" in sql
    assert "contracts.document_type IN" in sql
    assert plan_id in compiled.params.values()
