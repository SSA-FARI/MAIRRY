from ai.chat_agent.intent import ChatIntent
from ai.common.types import ToolCall


def decide_tool(intent: ChatIntent, arguments: dict[str, object] | None = None) -> ToolCall | None:
    tool_by_intent = {
        ChatIntent.CONTRACT: "getContractDetails",
        ChatIntent.SCHEDULE: "getUpcomingPayments",
        ChatIntent.FINANCE_SUMMARY: "getFinanceSummary",
        ChatIntent.EXPENSE_SIMULATION: "simulateAdditionalExpense",
    }
    tool_name = tool_by_intent.get(intent)
    if tool_name is None:
        return None
    return ToolCall(tool_name=tool_name, arguments=arguments or {})

