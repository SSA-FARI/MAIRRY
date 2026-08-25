from collections.abc import Callable

from ai.chat_agent.agent import decide_tool
from ai.chat_agent.intent import ChatIntent
from ai.chat_agent.response import explain_tool_result
from ai.common.types import ToolResultView

ToolExecutor = Callable[[str, dict[str, object], str], ToolResultView]


def process_chat(
    user_id: str,
    message: str,
    intent: ChatIntent,
    arguments: dict[str, object],
    execute_tool: ToolExecutor,
) -> str:
    call = decide_tool(intent, arguments)
    if call is None:
        return "계약, 지급 일정 또는 자금계획에 대해 질문해 주세요."

    result = execute_tool(call.tool_name, call.arguments, user_id)
    return explain_tool_result(message, result)

