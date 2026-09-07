import pytest

from ai.rag.routing import RagRoute, classify_rag_route


@pytest.mark.parametrize(
    "question",
    [
        "가전 비용 300만 원을 추가하면 괜찮아?",
        "300만원 더 쓰면 어떻게 돼?",
        "추가 지출 3,000,000원을 계산해줘",
        "일회성 비용을 300만원 더하면 부족해?",
    ],
)
def test_expense_simulation_routes_directly_to_tool(question: str) -> None:
    route, knowledge_types = classify_rag_route(question)

    assert route == RagRoute.TOOL
    assert knowledge_types == set()


def test_contract_additional_cost_clause_still_routes_to_rag() -> None:
    route, _knowledge_types = classify_rag_route("계약서의 추가 비용 조항을 알려줘")

    assert route == RagRoute.RAG
