from enum import StrEnum

from ai.rag.schemas import KnowledgeType


class RagRoute(StrEnum):
    TOOL = "TOOL"
    RAG = "RAG"
    MIXED = "MIXED"
    GENERAL = "GENERAL"


_CLAUSE_WORDS = ("취소", "환불", "위약금", "해지", "특약", "보증인원", "일정 변경", "추가 비용")
_FINANCE_WORDS = ("지급일", "잔금일", "결제일", "남은 금액", "예상 잔액", "가용자금", "추가 지출")
_FAQ_WORDS = ("로그인", "업로드", "확정하려면", "수정하려면", "삭제하려면", "사용법", "다시 시도")
_DOMAIN_WORDS = ("보증인원이 뭐", "스드메", "원본 구매", "수정본", "식대", "대관료", "뜻이")
_INJECTION_WORDS = (
    "이전 지시를 무시",
    "시스템 프롬프트",
    "다른 사용자의 계약서",
    "ignore previous instructions",
)


def classify_rag_route(question: str) -> tuple[RagRoute, set[KnowledgeType]]:
    has_clause = any(word in question for word in _CLAUSE_WORDS)
    has_finance = any(word in question for word in _FINANCE_WORDS)
    if has_clause and has_finance:
        return RagRoute.MIXED, {KnowledgeType.CONTRACT_CLAUSE}
    if has_clause:
        return RagRoute.RAG, {KnowledgeType.CONTRACT_CLAUSE, KnowledgeType.DOMAIN_KNOWLEDGE}
    if any(word in question for word in _FAQ_WORDS):
        return RagRoute.RAG, {KnowledgeType.SERVICE_FAQ}
    if any(word in question for word in _DOMAIN_WORDS):
        return RagRoute.RAG, {KnowledgeType.DOMAIN_KNOWLEDGE}
    if has_finance or "계약" in question:
        return RagRoute.TOOL, set()
    return RagRoute.GENERAL, set()


def rewrite_question(question: str, history: list[str]) -> str:
    normalized = " ".join(question.split())
    if history and any(token in normalized for token in ("그럼", "그 계약", "다음 달", "그때")):
        previous = " ".join(history[-1].split())
        return f"이전 질문({previous})에 이어서: {normalized}"
    return normalized


def expand_queries(question: str) -> list[str]:
    expansions = [question]
    synonyms = {
        "취소": "계약 해지 환불 위약금",
        "환불": "취소 반환 계약금 위약금",
        "보증인원": "최소 보증 인원 변경",
        "확정": "검수 계약 확정",
    }
    for keyword, expansion in synonyms.items():
        if keyword in question:
            candidate = f"{question} {expansion}"
            if candidate not in expansions:
                expansions.append(candidate)
        if len(expansions) >= 3:
            break
    return expansions


def contains_prompt_injection(text: str) -> bool:
    normalized = text.lower()
    return any(word in normalized for word in _INJECTION_WORDS)
