from ai.chat_agent.agent import decide_tool
from ai.chat_agent.intent import ChatIntent


def test_schedule_intent_selects_upcoming_payments() -> None:
    call = decide_tool(ChatIntent.SCHEDULE)
    assert call is not None
    assert call.tool_name == "getUpcomingPayments"


def test_expense_intent_preserves_arguments() -> None:
    call = decide_tool(
        ChatIntent.EXPENSE_SIMULATION,
        {"name": "가전 비용", "amount": 3_000_000},
    )
    assert call is not None
    assert call.tool_name == "simulateAdditionalExpense"
    assert call.arguments["amount"] == 3_000_000

