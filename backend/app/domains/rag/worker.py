import argparse
from uuid import UUID

from app.core.config import settings
from app.domains.rag.service import process_next_index_job, reconcile_index_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Process retryable RAG indexing jobs")
    parser.add_argument("--contract-id", type=UUID)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 1_000:
        parser.error("--limit must be between 1 and 1000")

    if args.contract_id is None:
        processed = reconcile_index_jobs(settings, limit=args.limit)
    else:
        processed = int(process_next_index_job(settings, contract_id=args.contract_id))
    print(f"processed={processed}")


if __name__ == "__main__":
    main()
