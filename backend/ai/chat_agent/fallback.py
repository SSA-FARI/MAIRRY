import re
from dataclasses import dataclass, field
from typing import Any

from ai.chat_agent.intent import ChatIntent

_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_AMOUNT_PATTERN = re.compile(
    r"(?P<expression>(?:\d[\d,]*\s*(?:억|만|천|백|십)+\s*)+|\d[\d,]*)\s*원"
)
_SMALL_UNIT_MULTIPLIERS = {"": 1, "십": 10, "백": 100, "천": 1_000}
_SMALL_NUMBER_PATTERN = re.compile(r"(?P<number>\d[\d,]*)\s*(?P<unit>천|백|십)?")


@dataclass(frozen=True)
class IntentDecision:
    intent: ChatIntent
    arguments: dict[str, Any] = field(default_factory=dict)


def classify_message(message: str) -> IntentDecision:
    normalized = " ".join(message.strip().split())
    contract_id = _extract_contract_id(normalized)

    if _contains_any(normalized, ("추가", "더 쓰", "구매", "사도", "지출")):
        amount_match = _AMOUNT_PATTERN.search(normalized)
        if amount_match is not None:
            arguments: dict[str, Any] = {
                "name": _extract_expense_name(normalized, amount_match),
                "amount": _parse_amount(amount_match),
            }
            return IntentDecision(ChatIntent.EXPENSE_SIMULATION, arguments)

    if _contains_any(
        normalized,
        ("남은 금액", "남은 지출", "예상 잔액", "가용 자금", "가용자금", "자금 현황"),
    ):
        return IntentDecision(ChatIntent.FINANCE_SUMMARY)

    if _contains_any(
        normalized,
        ("지급일", "잔금일", "납부일", "결제일", "지급 일정", "결제 일정", "언제"),
    ):
        arguments = {"limit": 1}
        if contract_id is not None:
            arguments["contractId"] = contract_id
        return IntentDecision(ChatIntent.SCHEDULE, arguments)

    if _contains_any(
        normalized,
        ("계약", "취소", "환불", "위약금", "업체", "웨딩홀"),
    ):
        arguments = {"contractId": contract_id} if contract_id is not None else {}
        return IntentDecision(ChatIntent.CONTRACT, arguments)

    return IntentDecision(ChatIntent.UNKNOWN)


def _contains_any(message: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in message for keyword in keywords)


def _extract_contract_id(message: str) -> str | None:
    match = _UUID_PATTERN.search(message)
    return match.group(0) if match is not None else None


def _parse_amount(match: re.Match[str]) -> int:
    expression = match.group("expression").replace(" ", "")
    if expression.count("억") > 1 or expression.count("만") > 1:
        raise ValueError("duplicate Korean amount unit")

    total = 0
    if "억" in expression:
        hundred_millions, expression = expression.split("억", maxsplit=1)
        total += _parse_small_number(hundred_millions) * 100_000_000
    if "만" in expression:
        ten_thousands, expression = expression.split("만", maxsplit=1)
        total += _parse_small_number(ten_thousands) * 10_000
    if expression:
        total += _parse_small_number(expression)
    return total


def _parse_small_number(expression: str) -> int:
    matches = list(_SMALL_NUMBER_PATTERN.finditer(expression))
    if not matches or "".join(match.group(0) for match in matches) != expression:
        raise ValueError("invalid Korean amount")
    return sum(
        int(match.group("number").replace(",", ""))
        * _SMALL_UNIT_MULTIPLIERS[match.group("unit") or ""]
        for match in matches
    )


def _extract_expense_name(message: str, amount_match: re.Match[str]) -> str:
    prefix = message[: amount_match.start()].strip(" ,")
    prefix = re.sub(r"^(만약|혹시|추가로)\s+", "", prefix)
    prefix = re.sub(r"(에|으로|로)$", "", prefix).strip()
    return prefix or "추가 지출"
