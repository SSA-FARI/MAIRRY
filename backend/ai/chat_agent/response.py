from ai.common.types import ToolResultView


def explain_tool_result(question: str, result: ToolResultView) -> str:
    if result.status != "SUCCESS":
        return "현재 확정된 정보만으로는 답변할 수 없습니다."
    return (
        "Backend Tool 결과를 바탕으로 답변을 생성해야 합니다. "
        f"tool={result.tool_name}, question={question}"
    )

