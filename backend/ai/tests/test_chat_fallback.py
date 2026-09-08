import pytest

from ai.chat_agent.fallback import classify_message
from ai.chat_agent.intent import ChatIntent


def test_fallback_classifies_supported_intents() -> None:
    assert classify_message("가장 가까운 잔금일은 언제야?").intent == ChatIntent.SCHEDULE
    assert classify_message("남은 금액과 예상 잔액 알려줘").intent == ChatIntent.FINANCE_SUMMARY
    assert classify_message("웨딩홀 취소 조건 알려줘").intent == ChatIntent.CONTRACT_CLAUSE_QA
    assert classify_message("오늘 날씨 알려줘").intent == ChatIntent.UNKNOWN


@pytest.mark.parametrize("message", ["안녕", "안녕하세요", "고마워", "무엇을 물어볼 수 있어?"])
def test_fallback_classifies_general_chat(message: str) -> None:
    assert classify_message(message).intent == ChatIntent.GENERAL_CHAT


def test_fallback_distinguishes_balance_contract_payment_and_follow_up() -> None:
    assert classify_message("남은 잔액 알려줘").intent == ChatIntent.FINANCE_SUMMARY
    assert classify_message("현재 우리 잔금 알려줘").intent == ChatIntent.NEEDS_CLARIFICATION
    assert classify_message("웨딩홀 잔금 알려줘").intent == ChatIntent.CONTRACT_PAYMENT
    assert classify_message("그럼 300만원 써도 되는 거야?").intent == ChatIntent.FOLLOW_UP


@pytest.mark.parametrize(
    "message",
    [
        "현재 내 스드메 계약 있나?",
        "내 스 드 메 계약이 있어?",
        "우리 스튜디오·드레스·메이크업 계약 현황 알려줘",
        "내가 올린 웨딩 촬영 패키지 계약서 있어?",
    ],
)
def test_fallback_classifies_personal_contract_ownership_lookup(message: str) -> None:
    assert classify_message(message).intent == ChatIntent.USER_CONTRACT_LOOKUP


def test_fallback_separates_domain_definition_and_personal_clause_question() -> None:
    assert classify_message("스드메가 뭐야?").intent == ChatIntent.DOMAIN_KNOWLEDGE
    assert classify_message("내 웨딩홀 계약 취소 조건은?").intent == ChatIntent.CONTRACT_CLAUSE_QA


def test_fallback_extracts_korean_expense_amount_without_recalculating_it() -> None:
    decision = classify_message("가전 비용 300만 원을 추가하면 괜찮아?")

    assert decision.intent == ChatIntent.EXPENSE_SIMULATION
    assert decision.arguments == {"name": "가전 비용", "amount": 3_000_000}


def test_fallback_accumulates_compound_korean_amount_units() -> None:
    cases = {
        "가전 300만원 추가": 3_000_000,
        "가전 3,000,000원 추가": 3_000_000,
        "가전 3000000원 추가": 3_000_000,
        "혼수 1억원 추가": 100_000_000,
        "혼수 3억 5천만 원 추가": 350_000_000,
        "예식 1억 2백만 원 추가": 102_000_000,
        "가전 5천 3백만 원 추가": 53_000_000,
    }

    for message, expected_amount in cases.items():
        decision = classify_message(message)
        assert decision.intent == ChatIntent.EXPENSE_SIMULATION
        assert decision.arguments["amount"] == expected_amount


@pytest.mark.parametrize(
    ("message", "expected_name"),
    [
        ("300만 원을 추가하면", "추가 지출"),
        ("300만원 더 쓰면", "추가 지출"),
        ("가전 비용 300만 원을 추가하면", "가전 비용"),
        ("추가 지출 3,000,000원을 계산해줘", "추가 지출"),
        ("300만원을 지출하면", "추가 지출"),
        ("일회성 비용을 300만원 더하면", "일회성 비용"),
    ],
)
def test_fallback_recognizes_expense_simulation_phrasings(message: str, expected_name: str) -> None:
    decision = classify_message(message)

    assert decision.intent == ChatIntent.EXPENSE_SIMULATION
    assert decision.arguments == {"name": expected_name, "amount": 3_000_000}


@pytest.mark.parametrize(
    "message",
    [
        "가전 비용을 추가하면 괜찮아?",
        "추가 지출 0원 계산해줘",
        "추가 지출 -300만원 계산해줘",
        "가전 300만원과 가구 200만원을 추가하면?",
        "추가 지출 NaN원을 계산해줘",
        "추가 지출 Infinity원을 계산해줘",
        "추가 지출 1억 2억원을 계산해줘",
    ],
)
def test_fallback_does_not_invent_ambiguous_or_invalid_simulation_amounts(message: str) -> None:
    assert classify_message(message).intent == ChatIntent.UNKNOWN
