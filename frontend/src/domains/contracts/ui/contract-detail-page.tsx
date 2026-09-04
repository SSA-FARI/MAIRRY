"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/shared/api/api-client";
import { formatDate } from "@/shared/lib/date";
import { formatWon } from "@/shared/lib/money";
import { AppHeader } from "@/shared/ui/app-header";
import { StatusBadge } from "@/shared/ui/status-badge";
import type { PaymentStatus } from "@/domains/documents";
import { deleteContract, getContract, updatePaymentStatus } from "../api/contracts-api";
import type { ContractDetail } from "../model/types";

const PAYMENT_STATUS_META = {
  PAID: { label: "지급 완료", tone: "success" },
  UNPAID: { label: "미지급", tone: "primary" },
  UNKNOWN: { label: "확인 필요", tone: "warning" },
} as const;

export function ContractDetailPage({ contractId }: { contractId: string }) {
  const router = useRouter();
  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [updatingPaymentId, setUpdatingPaymentId] = useState<string | null>(null);
  const [paymentError, setPaymentError] = useState("");

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

  async function handlePaymentStatusChange(paymentId: string, nextStatus: PaymentStatus) {
    if (!contract || updatingPaymentId) return;
    setUpdatingPaymentId(paymentId);
    setPaymentError("");
    try {
      setContract(await updatePaymentStatus(contractId, paymentId, nextStatus));
    } catch (error) {
      setPaymentError(
        error instanceof ApiError
          ? error.message
          : "지급상태를 변경하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setUpdatingPaymentId(null);
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
    <div className="app-shell">
      <AppHeader active="contracts" />
      <main className="content-page">
        <nav className="page-nav" aria-label="계약 화면 탐색">
          <Link href="/contracts">계약 관리</Link>
          <span aria-hidden="true">/</span>
          <span>{contract.company}</span>
        </nav>
        <header className="detail-hero">
          <div>
            <StatusBadge tone="success">확정 계약</StatusBadge>
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
          <p className="section-description">
            실제 지급 여부가 바뀌면 상태를 바로 변경하세요. 미지급 금액만 자금 현황에 반영됩니다.
          </p>
          {paymentError && (
            <p role="alert" className="page-error">
              {paymentError}
            </p>
          )}
          <div className="detail-list">
            {contract.payments.map((payment) => (
              <article className="detail-item" key={payment.id}>
                <div className="detail-item-main">
                  <div>
                    <StatusBadge
                      tone={PAYMENT_STATUS_META[payment.status].tone}
                      className="payment-status"
                    >
                      {PAYMENT_STATUS_META[payment.status].label}
                    </StatusBadge>
                    <h3>{payment.name}</h3>
                    <p>{formatDate(payment.dueDate)}</p>
                  </div>
                  <div className="payment-item-actions">
                    <strong>{formatWon(payment.amount)}</strong>
                    <label>
                      <span className="sr-only">{payment.name} 지급상태</span>
                      <select
                        aria-label={`${payment.name} 지급상태`}
                        value={payment.status}
                        disabled={updatingPaymentId !== null}
                        onChange={(event) =>
                          void handlePaymentStatusChange(
                            payment.id,
                            event.target.value as PaymentStatus,
                          )
                        }
                      >
                        <option value="UNPAID">미지급</option>
                        <option value="PAID">지급 완료</option>
                        <option value="UNKNOWN">확인 필요</option>
                      </select>
                    </label>
                    {updatingPaymentId === payment.id && (
                      <span className="payment-update-status" role="status">
                        변경 중…
                      </span>
                    )}
                  </div>
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
    </div>
  );
}
