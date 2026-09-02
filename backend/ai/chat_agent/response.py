from dataclasses import dataclass, field
from typing import Any, Literal

from ai.common.types import ToolResultView

AnswerTypeValue = Literal["CONTRACT", "CALCULATION", "NOT_FOUND"]


@dataclass(frozen=True)
class AnswerDraft:
    answer: str
    answer_type: AnswerTypeValue
    citations: list[dict[str, Any]] = field(default_factory=list)
    calculation: dict[str, Any] | None = None


def explain_tool_result(question: str, result: ToolResultView) -> AnswerDraft:
    if result.status != "SUCCESS" or result.data is None:
        return AnswerDraft(
            answer=_failure_answer(result),
            answer_type="NOT_FOUND",
        )

    handlers = {
        "getContractDetails": _explain_contract,
        "getUpcomingPayments": _explain_schedule,
        "getFinanceSummary": _explain_finance,
        "simulateAdditionalExpense": _explain_simulation,
    }
    handler = handlers.get(result.tool_name)
    if handler is None:
        return AnswerDraft(
            answer="지원하지 않는 질문입니다. 계약, 지급 일정 또는 자금계획을 질문해 주세요.",
            answer_type="NOT_FOUND",
        )
    return handler(question, result)


def _failure_answer(result: ToolResultView) -> str:
    messages = {
        "NOT_FOUND": "요청한 확정 정보를 찾지 못했습니다.",
        "INSUFFICIENT_DATA": "답변에 필요한 웨딩 계획 정보가 없습니다.",
        "INVALID_ARGUMENT": "질문에 필요한 정보를 조금 더 구체적으로 입력해 주세요.",
        "TOOL_ERROR": "정보를 조회하는 중 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    }
    return messages.get(result.status, "현재 확정된 정보만으로는 답변할 수 없습니다.")


def _explain_contract(question: str, result: ToolResultView) -> AnswerDraft:
    assert result.data is not None
    company = str(result.data["company"])
    if any(keyword in question for keyword in ("취소", "환불", "위약금")):
        terms = result.data.get("cancellationTerms", [])
        if not terms:
            return AnswerDraft(
                answer=f"{company} 계약에서 확인된 취소·환불 조건이 없습니다.",
                answer_type="NOT_FOUND",
            )
        summaries = [str(term["summary"]) for term in terms]
        citations = [
            evidence
            for evidence in result.evidence
            if str(evidence.get("label", "")).endswith("취소조건")
        ]
        return AnswerDraft(
            answer=f"{company} 취소·환불 조건은 {'; '.join(summaries)}입니다.",
            answer_type="CONTRACT",
            citations=citations,
        )

    total_price = _won(result.data["totalPrice"])
    return AnswerDraft(
        answer=f"{company} 계약 총액은 {total_price}원입니다.",
        answer_type="CONTRACT",
        citations=list(result.evidence),
    )


def _explain_schedule(_question: str, result: ToolResultView) -> AnswerDraft:
    assert result.data is not None
    payments = result.data.get("payments", [])
    if not payments:
        return AnswerDraft(
            answer="조건에 맞는 미지급 일정을 찾지 못했습니다.",
            answer_type="NOT_FOUND",
        )
    descriptions = [
        f"{payment['company']} {payment['name']}은 {payment['dueDate']}, "
        f"{_won(payment['amount'])}원"
        for payment in payments
    ]
    return AnswerDraft(
        answer=f"가까운 지급 일정은 {'; '.join(descriptions)}입니다.",
        answer_type="CONTRACT",
        citations=list(result.evidence),
    )


def _explain_finance(_question: str, result: ToolResultView) -> AnswerDraft:
    assert result.data is not None
    data = result.data
    answer = (
        f"현재 가용자금은 {_won(data['availableAsset'])}원, "
        f"남은 확정지출은 {_won(data['remainingExpense'])}원, "
        f"예상 잔액은 {_won(data['expectedBalance'])}원입니다."
    )
    return AnswerDraft(
        answer=answer,
        answer_type="CALCULATION",
        calculation={
            "tool_name": result.tool_name,
            "available_asset": data["availableAsset"],
            "remaining_expense": data["remainingExpense"],
            "expected_balance": data["expectedBalance"],
            "calculated_at": result.calculated_at,
        },
    )


def _explain_simulation(_question: str, result: ToolResultView) -> AnswerDraft:
    assert result.data is not None
    data = result.data
    shortage = int(data["shortageAmount"])
    shortage_text = "부족액은 없습니다" if shortage == 0 else f"부족액은 {_won(shortage)}원입니다"
    additional_amount = int(data["currentExpectedBalance"]) - int(data["simulatedExpectedBalance"])
    answer = (
        f"{data['name']} {_won(additional_amount)}원을 추가하면 "
        f"예상 잔액은 {_won(data['simulatedExpectedBalance'])}원이며, {shortage_text}."
    )
    return AnswerDraft(
        answer=answer,
        answer_type="CALCULATION",
        calculation={
            "tool_name": result.tool_name,
            "current_expected_balance": data["currentExpectedBalance"],
            "simulated_expected_balance": data["simulatedExpectedBalance"],
            "shortage_amount": data["shortageAmount"],
            "calculated_at": result.calculated_at,
        },
    )


def _won(value: object) -> str:
    return f"{int(value):,}"
