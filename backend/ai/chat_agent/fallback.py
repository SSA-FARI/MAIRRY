import re
from dataclasses import dataclass, field
from typing import Any

from ai.chat_agent.intent import ChatIntent

_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_AMOUNT_PATTERN = re.compile(r"(?P<number>\d[\d,]*)\s*(?P<unit>억|천만|백만|십만|만)?\s*원")
_UNIT_MULTIPLIERS = {
    None: 1,
    "만": 10_000,
    "십만": 100_000,
    "백만": 1_000_000,
    "천만": 10_000_000,
    "억": 100_000_000,
}


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
    number = int(match.group("number").replace(",", ""))
    return number * _UNIT_MULTIPLIERS[match.group("unit")]


def _extract_expense_name(message: str, amount_match: re.Match[str]) -> str:
    prefix = message[: amount_match.start()].strip(" ,")
    prefix = re.sub(r"^(만약|혹시|추가로)\s+", "", prefix)
    prefix = re.sub(r"(에|으로|로)$", "", prefix).strip()
    return prefix or "추가 지출"
