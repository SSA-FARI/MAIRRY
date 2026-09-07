# RAG 임베딩 데이터셋

벡터 DB 임베딩을 전제로 한 시드 데이터셋이다. 현재 백엔드에는 RAG 파이프라인이 구현되어
있지 않으며(`backend/ai/chat_agent`는 Tool Calling 기반 답변만 수행), 이 디렉터리는 향후
RAG 도입 시 사용할 데이터 형태와 청킹 단위를 미리 정의해 둔 것이다.

RAG 도입 시 파이프라인이 어디에 끼워지는지, 사용자 업로드 계약서를 임베딩하기 전 어떤
개인정보를 마스킹해야 하는지는 [docs/05_ARCHITECTURE.md의 "RAG 임베딩 확장"](../../../../docs/05_ARCHITECTURE.md#rag-임베딩-확장-향후-현재-mvp-범위-아님) 절을 따른다.
`contract-clause-chunks.jsonl`은 그 마스킹 이후 형태를 흉내 낸 데모 샘플이 아니라, 청킹
단위와 메타데이터 스키마만 보여주는 예시임에 유의한다(실제 파이프라인에서는 마스킹을 거친다).

## 파일 구성

| 파일 | 용도 | 우선순위 |
|---|---|---|
| [contract-clause-chunks.jsonl](contract-clause-chunks.jsonl) | 계약서 원문 자유 텍스트 조항(특약사항·환불/위약금·해지조건) 청크. 실제 서비스에서는 사용자가 업로드한 계약서마다 런타임으로 생성되는 컬렉션이며, 이 파일은 데모/개발용 샘플이다 | 높음 |
| [domain-glossary.jsonl](domain-glossary.jsonl) | 웨딩홀·스드메 업계 계약 용어 및 관행 지식베이스 | 높음 |
| [service-faq.jsonl](service-faq.jsonl) | MAIRRY 서비스 사용법(회원가입, 업로드, 검수·확정, 대시보드 등) FAQ | 중간 |
| [consultation-history.jsonl](consultation-history.jsonl) | 과거 상담 질문-답변 예시. MVP 단계에서는 데이터가 적어 우선순위 낮음 | 낮음 |

## 공통 스키마 (JSONL, 1행 = 1청크)

```json
{
  "id": "컬렉션 내 고유 ID",
  "category": "clause | glossary | faq | consultation",
  "text": "임베딩 대상 본문 (질문에 근거로 인용될 수 있는 단위)",
  "metadata": { "...": "카테고리별 부가 필드" }
}
```

- `text`는 임베딩 모델에 그대로 입력하는 필드다. 조항형 데이터는 원문을 요약하지 않고
  그대로 담아, `sourceText` 인용이 필요한 질문(citations)에 근거로 쓸 수 있게 한다.
- `metadata`는 벡터 DB에 함께 저장해 필터링·인용 표시에 사용한다. 계약 조항 청크의
  `contractId`/`sourceDocument`는 실제 연동 시 `Document`/`Contract` 테이블의 ID로 치환한다.
- 파일 인코딩은 UTF-8, 줄바꿈은 LF다.
