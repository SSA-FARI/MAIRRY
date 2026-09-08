import re
from typing import Any

from ai.chat_agent.intent import ChatIntent
from ai.chat_agent.schemas import IntentDecision

_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_AMOUNT_PATTERN = re.compile(
    r"(?P<expression>(?:\d[\d,]*\s*(?:억|만|천|백|십)+\s*)+|\d[\d,]*)\s*원"
)
_SMALL_UNIT_MULTIPLIERS = {"": 1, "십": 10, "백": 100, "천": 1_000}
_SMALL_NUMBER_PATTERN = re.compile(r"(?P<number>\d[\d,]*)\s*(?P<unit>천|백|십)?")
_SIMULATION_ACTIONS = ("추가", "더 쓰", "더하", "구매", "사도", "써도", "지출", "사용")
_GENERAL_GREETINGS = ("안녕", "안녕하세요", "반가워", "반가워요", "반갑습니다")
_GENERAL_THANKS = ("고마워", "고마워요", "고맙습니다", "감사해", "감사해요", "감사합니다")
_GENERAL_HELP = ("어떤 걸 물어볼 수 있어", "무엇을 물어볼 수 있어", "뭘 물어볼 수 있어")
_FOLLOW_UP_MARKERS = ("그럼", "그러면", "그래도", "그 금액", "그거")
_CALCULATION_FOLLOW_UP_WORDS = ("써도", "사용해도", "괜찮", "부족", "얼마 남", "잔액", "금액")
_CONTRACT_TARGETS = ("계약별", "계약", "웨딩홀", "스튜디오", "드레스", "메이크업", "업체")
_CONTRACT_CLAUSE_WORDS = ("취소", "환불", "위약금", "해지", "특약", "보증인원", "일정 변경")
_CONTRACT_LOOKUP_TARGETS = (
    "계약",
    "계약서",
    "스드메",
    "스 드 메",
    "스튜디오",
    "드레스",
    "메이크업",
    "웨딩홀",
    "촬영 패키지",
)
_CONTRACT_LOOKUP_MARKERS = (
    "내 ",
    "내가 ",
    "우리 ",
    "현재 ",
    "보유",
    "등록한",
    "등록된",
    "올린",
    "확정한",
    "있나",
    "있어",
    "있는지",
    "목록",
    "현황",
    "상태",
    "확정됐",
)


def classify_message(message: str) -> IntentDecision:
    normalized = " ".join(message.strip().split())
    contract_id = _extract_contract_id(normalized)

    general_phrase = normalized.rstrip("!?., ")
    if general_phrase in _GENERAL_GREETINGS + _GENERAL_THANKS or _contains_any(
        normalized, _GENERAL_HELP
    ):
        return _decision(ChatIntent.GENERAL_CHAT)

    if _contains_any(normalized, _FOLLOW_UP_MARKERS) and _contains_any(
        normalized, _CALCULATION_FOLLOW_UP_WORDS
    ):
        return _decision(ChatIntent.FOLLOW_UP)

    if (
        "잔금" in normalized
        and "잔금일" not in normalized
        and not _contains_any(normalized, _CONTRACT_TARGETS)
    ):
        return _decision(ChatIntent.NEEDS_CLARIFICATION)

    if _contains_any(
        normalized,
        ("예약금", "계약금", "선금", "첫 납부금", "초기 납부금", "1차 납부금"),
    ):
        arguments = {"contractId": contract_id} if contract_id is not None else {}
        return _decision(ChatIntent.CONTRACT_DEPOSIT, arguments)

    if looks_like_expense_simulation(normalized):
        amount_matches = list(_AMOUNT_PATTERN.finditer(normalized))
        if len(amount_matches) == 1:
            amount_match = amount_matches[0]
            try:
                amount = _parse_amount(amount_match)
            except ValueError:
                return _decision(ChatIntent.UNKNOWN)
            if amount <= 0 or _has_negative_sign(normalized, amount_match):
                return _decision(ChatIntent.UNKNOWN)
            arguments: dict[str, Any] = {
                "name": _extract_expense_name(normalized, amount_match),
                "amount": amount,
            }
            return _decision(ChatIntent.EXPENSE_SIMULATION, arguments)

    if _contains_any(
        normalized,
        (
            "남은 금액",
            "남은 지출",
            "남은 잔액",
            "예상 잔액",
            "가용 자금",
            "가용자금",
            "자금 현황",
        ),
    ):
        return _decision(ChatIntent.FINANCE_SUMMARY)

    if _looks_like_user_contract_lookup(normalized):
        return _decision(ChatIntent.USER_CONTRACT_LOOKUP)

    if _contains_any(
        normalized,
        ("지급일", "잔금일", "납부일", "결제일", "지급 일정", "결제 일정", "언제"),
    ):
        arguments = {"limit": 1}
        if contract_id is not None:
            arguments["contractId"] = contract_id
        return _decision(ChatIntent.SCHEDULE, arguments)

    if "잔금" in normalized:
        arguments = {"contractId": contract_id} if contract_id is not None else {}
        return _decision(ChatIntent.CONTRACT_PAYMENT, arguments)

    if _contains_any(normalized, _CONTRACT_CLAUSE_WORDS):
        return _decision(ChatIntent.CONTRACT_CLAUSE_QA)

    if _contains_any(normalized, ("로그인", "업로드", "사용법", "다시 시도")):
        return _decision(ChatIntent.SERVICE_FAQ)

    if _contains_any(normalized, ("뭐야", "무슨 뜻", "뜻이")):
        return _decision(ChatIntent.DOMAIN_KNOWLEDGE)

    if _contains_any(
        normalized,
        ("계약", "취소", "환불", "위약금", "업체", "웨딩홀"),
    ):
        arguments = {"contractId": contract_id} if contract_id is not None else {}
        return _decision(ChatIntent.CONTRACT, arguments)

    return _decision(ChatIntent.UNKNOWN)


def _looks_like_user_contract_lookup(message: str) -> bool:
    if _contains_any(message, _CONTRACT_CLAUSE_WORDS):
        return False
    compact = re.sub(r"[\s·ㆍ/]", "", message)
    has_target = _contains_any(message, _CONTRACT_LOOKUP_TARGETS) or "스드메" in compact
    return has_target and _contains_any(message, _CONTRACT_LOOKUP_MARKERS)


def _decision(intent: ChatIntent, arguments: dict[str, Any] | None = None) -> IntentDecision:
    return IntentDecision(intent, arguments)


def _contains_any(message: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in message for keyword in keywords)


def looks_like_expense_simulation(message: str) -> bool:
    """Identify hypothetical spending language before intent/tool selection."""
    normalized = " ".join(message.strip().split())
    if not _contains_any(normalized, _SIMULATION_ACTIONS):
        return False
    if _AMOUNT_PATTERN.search(normalized) or re.search(r"(?:NaN|Infinity)\s*원", normalized):
        return True
    return _contains_any(
        normalized,
        ("추가하면", "추가할", "더 쓰", "더하면", "지출하면", "사용하면", "계산해"),
    )


def _has_negative_sign(message: str, amount_match: re.Match[str]) -> bool:
    return message[: amount_match.start()].rstrip().endswith("-")


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
    prefix = re.sub(r"(에|으로|로|을|를)$", "", prefix).strip()
    return prefix or "추가 지출"
