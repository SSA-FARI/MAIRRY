import hashlib
import re
from dataclasses import dataclass

from ai.rag.schemas import KnowledgeType, RagChunk

_ARTICLE_HEADING = r"제[ \t]*\d+[ \t]*조(?:의[ \t]*\d+)?(?:[ \t]*\([^\n)]{1,60}\))?"
_NUMBERED_SPECIAL_TERM_HEADING = r"특약(?:사항)?[ \t]+(?:제[ \t]*)?\d+[ \t]*(?:조|항)?[.)]?"
_BARE_SPECIAL_TERM_HEADING = r"특약(?:사항)?"
_SECTION_HEADING = r"\d{1,2}\.[ \t]+[^\n.!?。！？:：]{1,60}"
_TOPIC_HEADING = (
    r"(?:환불|취소|계약[ \t]*해지|일정[ \t]*변경|보증[ \t]*인원|"
    r"추가[ \t]*비용|책임[ \t]*제한)"
    r"(?:[ \t]*(?:조건|규정|기준|정책|조항|사항|안내))?"
)
_HEADING_PATTERN = re.compile(
    rf"(?mx)^[ \t]*(?:[-•][ \t]*)?(?P<title>(?:"
    rf"(?:{_ARTICLE_HEADING}|{_NUMBERED_SPECIAL_TERM_HEADING})"
    rf"(?=[ \t]*(?::|：|$)|[ \t]+\S)|"
    rf"{_BARE_SPECIAL_TERM_HEADING}(?=[ \t]*(?::|：|$))|"
    rf"{_SECTION_HEADING}(?=[ \t]*$)|"
    rf"{_TOPIC_HEADING}(?=[ \t]*(?::|：|$))"
    rf"))"
)
_PAGE_ONLY = re.compile(r"^\s*(?:-\s*)?\d{1,3}(?:\s*-)?\s*$")


@dataclass(frozen=True)
class ClauseSource:
    title: str
    content: str
    clause_title: str | None = None
    page: int | None = None


def normalize_contract_text(value: str) -> str:
    lines = [" ".join(line.split()) for line in value.replace("\r\n", "\n").split("\n")]
    frequencies = {line: lines.count(line) for line in set(lines) if line}
    return "\n".join(
        line
        for line in lines
        if line and not _PAGE_ONLY.fullmatch(line) and frequencies.get(line, 0) <= 2
    ).strip()


def split_structured_clauses(text: str) -> list[ClauseSource]:
    normalized = normalize_contract_text(text)
    if not normalized:
        return []
    matches = list(_HEADING_PATTERN.finditer(normalized))
    if not matches:
        return [ClauseSource(title="계약 조항", content=normalized)]
    clauses: list[ClauseSource] = []
    prefix = normalized[: matches[0].start()].strip()
    if prefix:
        clauses.append(ClauseSource(title="계약 조항", content=prefix))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        title = " ".join(match.group("title").split())
        clauses.append(
            ClauseSource(
                title=title, clause_title=title, content=normalized[match.start() : end].strip()
            )
        )
    return clauses


def chunk_clause_sources(
    sources: list[ClauseSource],
    *,
    knowledge_type: KnowledgeType,
    namespace: str,
    chunk_size: int,
    overlap: int,
) -> list[RagChunk]:
    if overlap >= chunk_size:
        raise ValueError("chunk overlap must be smaller than chunk size")
    chunks: list[RagChunk] = []
    for source in sources:
        content = normalize_contract_text(source.content)
        if not content:
            continue
        pieces = _split_long_text(content, chunk_size, overlap)
        for piece in pieces:
            content_hash = hashlib.sha256(piece.encode("utf-8")).hexdigest()
            chunk_id = hashlib.sha256(
                f"{namespace}:{knowledge_type}:{source.title}:{content_hash}".encode()
            ).hexdigest()
            chunks.append(
                RagChunk(
                    chunk_id=chunk_id,
                    content_hash=content_hash,
                    content=piece,
                    knowledge_type=knowledge_type,
                    title=source.title,
                    clause_title=source.clause_title,
                    page=source.page,
                    chunk_index=len(chunks),
                )
            )
    return chunks


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return pieces
