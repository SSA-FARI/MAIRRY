"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/shared/api/api-client";
import { formatDate } from "@/shared/lib/date";
import { formatWon } from "@/shared/lib/money";
import { deleteContract, getContract } from "../api/contracts-api";
import type { ContractDetail } from "../model/types";

export function ContractDetailPage({ contractId }: { contractId: string }) {
  const router = useRouter();
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage("");
    try {
      setContract(await getContract(contractId));
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : "계약 상세를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [contractId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleDelete() {
    if (isDeleting || !contract) return;
    const confirmed = window.confirm(
      "계약을 삭제하면 자금 현황에서 제외됩니다. 원본 문서는 보존되며 다시 검수할 수 있습니다. 삭제할까요?",
    );
    if (!confirmed) return;

    setIsDeleting(true);
    setDeleteError("");
    try {
      await deleteContract(contractId);
      router.push("/contracts");
    } catch (error) {
      setDeleteError(
        error instanceof ApiError
          ? error.message
          : "계약을 삭제하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setIsDeleting(false);
    }
  }

  if (isLoading) {
    return (
      <main className="content-page">
        <section className="state-card" role="status">
          계약 상세를 불러오는 중입니다…
        </section>
      </main>
    );
  }

  if (!contract) {
    return (
      <main className="content-page">
        <section className="state-card" role="alert">
          <p>{errorMessage}</p>
          <button type="button" className="secondary-button" onClick={() => void load()}>
            다시 시도
          </button>
          <Link href="/contracts" className="text-link">
            계약 목록으로
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="content-page">
      <nav className="page-nav" aria-label="계약 화면 탐색">
        <Link href="/contracts">계약 관리</Link>
        <span aria-hidden="true">/</span>
        <span>{contract.company}</span>
      </nav>
      <header className="detail-hero">
        <div>
          <span className="status-badge">확정 계약</span>
          <h1>{contract.company}</h1>
          <p>{contract.documentType === "WEDDING_HALL" ? "웨딩홀 계약" : "기타 계약"}</p>
        </div>
        <div className="detail-total">
          <span>계약 총액</span>
          <strong>{formatWon(contract.totalPrice)}</strong>
        </div>
      </header>

      <div className="detail-actions" aria-label="계약 관리 작업">
        <Link href={`/contracts/${contractId}/edit`} className="secondary-link">
          계약 수정
        </Link>
        <button
          type="button"
          className="danger-button"
          disabled={isDeleting}
          onClick={() => void handleDelete()}
        >
          {isDeleting ? "삭제하는 중…" : "계약 삭제"}
        </button>
      </div>
      {deleteError && (
        <p role="alert" className="page-error">
          {deleteError}
        </p>
      )}

      <section className="detail-section" aria-labelledby="payments-title">
        <div className="section-heading">
          <h2 id="payments-title">지급항목</h2>
          <span>{contract.payments.length}건</span>
        </div>
        <div className="detail-list">
          {contract.payments.map((payment, index) => (
            <article className="detail-item" key={`${payment.name}-${index}`}>
              <div className="detail-item-main">
                <div>
                  <span className={`payment-status payment-status-${payment.status.toLowerCase()}`}>
                    {payment.status === "PAID"
                      ? "지급 완료"
                      : payment.status === "UNPAID"
                        ? "미지급"
                        : "확인 필요"}
                  </span>
                  <h3>{payment.name}</h3>
                  <p>{formatDate(payment.dueDate)}</p>
                </div>
                <strong>{formatWon(payment.amount)}</strong>
              </div>
              {payment.sourceText && (
                <blockquote>
                  <span>계약서 근거</span>
                  {payment.sourceText}
                </blockquote>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="detail-section" aria-labelledby="cancellations-title">
        <div className="section-heading">
          <h2 id="cancellations-title">취소조건</h2>
          <span>{contract.cancellationTerms.length}건</span>
        </div>
        {contract.cancellationTerms.length === 0 ? (
          <p className="muted-panel">등록된 취소조건이 없습니다.</p>
        ) : (
          <div className="detail-list">
            {contract.cancellationTerms.map((term, index) => (
              <article className="detail-item" key={`${term.summary}-${index}`}>
                <h3>{term.summary}</h3>
                {term.sourceText && (
                  <blockquote>
                    <span>계약서 근거</span>
                    {term.sourceText}
                  </blockquote>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
