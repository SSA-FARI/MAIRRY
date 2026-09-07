import argparse
from uuid import UUID

from app.core.config import settings
from app.core.database import SessionLocal
from app.domains.rag.repository import RagRepository
from app.domains.rag.service import process_contract_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Process retryable RAG indexing jobs")
    parser.add_argument("--contract-id", type=UUID)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 1_000:
        parser.error("--limit must be between 1 and 1000")

    if args.contract_id is not None:
        contract_ids = [args.contract_id]
    else:
        session = SessionLocal()
        try:
            contract_ids = RagRepository(session).list_retryable_contract_ids(args.limit)
        finally:
            session.close()
    for contract_id in contract_ids:
        process_contract_index(contract_id, settings)
    print(f"processed={len(contract_ids)}")


if __name__ == "__main__":
    main()
