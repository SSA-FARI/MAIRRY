"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/shared/api/api-client";
import { formatDate } from "@/shared/lib/date";
import { formatWon } from "@/shared/lib/money";
import { listContracts } from "../api/contracts-api";
import type { ContractSummary } from "../model/types";

type LoadState = "loading" | "success" | "error";

export function ContractListPage() {
  const [state, setState] = useState<LoadState>("loading");
  const [items, setItems] = useState<ContractSummary[]>([]);
  const [errorMessage, setErrorMessage] = useState("");

  const load = useCallback(async () => {
    setState("loading");
    try {
      const response = await listContracts();
      setItems(response.items);
      setState("success");
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : "계약 목록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
      setState("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <main className="content-page">
      <nav className="page-nav" aria-label="계약 화면 탐색">
        <Link href="/">대시보드</Link>
        <span aria-hidden="true">/</span>
        <span>계약 관리</span>
      </nav>
      <header className="page-header page-header-row">
        <div>
          <p className="eyebrow">CONTRACTS</p>
          <h1>확정 계약</h1>
          <p>검수를 마치고 자금 계획에 반영된 계약만 표시합니다.</p>
        </div>
        <Link href="/documents/upload" className="primary-link">
          계약서 추가
        </Link>
      </header>

      {state === "loading" && (
        <section className="state-card" role="status" aria-live="polite">
          계약 목록을 불러오는 중입니다…
        </section>
      )}
      {state === "error" && (
        <section className="state-card" role="alert">
          <p>{errorMessage}</p>
          <button type="button" className="secondary-button" onClick={() => void load()}>
            다시 시도
          </button>
        </section>
      )}
      {state === "success" && items.length === 0 && (
        <section className="state-card empty-state">
          <h2>아직 확정된 계약이 없습니다</h2>
          <p>계약서를 업로드하고 추출 내용을 확인하면 이곳에서 관리할 수 있어요.</p>
          <Link href="/documents/upload" className="primary-link">
            첫 계약서 등록
          </Link>
        </section>
      )}
      {state === "success" && items.length > 0 && (
        <section className="contract-grid" aria-label="확정 계약 목록">
          {items.map((contract) => (
            <article className="contract-card" key={contract.id}>
              <div className="contract-card-heading">
                <div>
                  <span className="status-badge">확정</span>
                  <h2>{contract.company}</h2>
                </div>
                <strong>{formatWon(contract.totalPrice)}</strong>
              </div>
              <div className="next-payment">
                <span>다음 지급</span>
                {contract.nextPayment ? (
                  <p>
                    {formatDate(contract.nextPayment.dueDate)} · {contract.nextPayment.name}
                    <strong>{formatWon(contract.nextPayment.amount)}</strong>
                  </p>
                ) : (
                  <p>예정된 미지급 일정이 없습니다.</p>
                )}
              </div>
              <Link href={`/contracts/${contract.id}`} className="text-link">
                계약 상세 보기 →
              </Link>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
