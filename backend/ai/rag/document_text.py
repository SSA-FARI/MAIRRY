from io import BytesIO

from pypdf import PdfReader

from ai.rag.chunking import ClauseSource, split_structured_clauses


def extract_pdf_clause_sources(content: bytes) -> list[ClauseSource]:
    sources: list[ClauseSource] = []
    reader = PdfReader(BytesIO(content))
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for clause in split_structured_clauses(text):
            sources.append(
                ClauseSource(
                    title=clause.title,
                    content=clause.content,
                    clause_title=clause.clause_title,
                    page=page_number,
                )
            )
    return sources
