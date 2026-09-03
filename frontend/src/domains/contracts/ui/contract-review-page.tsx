"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { analyzeDocument, getDocument } from "@/domains/documents";
import type { DocumentDetail, PaymentStatus } from "@/domains/documents";
import { ApiError } from "@/shared/api/api-client";
import { formatWon } from "@/shared/lib/money";
import { confirmDocument, getContract, updateContract } from "../api/contracts-api";
import {
  createContractForm,
  createReviewForm,
  hasReviewErrors,
  toContractConfirm,
  validateReviewForm,
  type ContractReviewForm,
  type ReviewValidationErrors,
} from "../model/review-form";

type PageState = "loading" | "analyzing" | "timeout" | "ready" | "confirmed" | "error";

const emptyErrors: ReviewValidationErrors = {
  paymentFields: {},
  cancellationFields: {},
};

const ANALYSIS_POLL_INTERVAL_MS = 1000;
const ANALYSIS_POLL_TIMEOUT_MS = 60000;

export function ContractReviewPage({ documentId }: { documentId: string }) {
  return <ContractFormPage documentId={documentId} />;
}

export function ContractEditPage({ contractId }: { contractId: string }) {
  return <ContractFormPage contractId={contractId} />;
}

type ContractFormPageProps =
  { documentId: string; contractId?: never } | { contractId: string; documentId?: never };

function ContractFormPage({ documentId, contractId }: ContractFormPageProps) {
  const router = useRouter();
  const isEditing = contractId !== undefined;
  const [pageState, setPageState] = useState<PageState>("loading");
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [form, setForm] = useState<ContractReviewForm | null>(null);
  const [validationErrors, setValidationErrors] = useState<ReviewValidationErrors>(emptyErrors);
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [isRetryingAnalysis, setIsRetryingAnalysis] = useState(false);
  const [retryErrorMessage, setRetryErrorMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const pollStartedAt = Date.now();

    async function load() {
      try {
        if (contractId !== undefined) {
          const contract = await getContract(contractId);
          if (cancelled) return;
          setForm(createContractForm(contract));
          setPageState("ready");
          return;
        }
        if (documentId === undefined) return;
        let current = await getDocument(documentId);
        if (cancelled) return;

        if (current.status === "UPLOADED") {
          current = await analyzeDocument(documentId);
          if (cancelled) return;
        }

        setDocument(current);
        if (current.status === "PROCESSING" || current.status === "UPLOADED") {
          if (Date.now() - pollStartedAt >= ANALYSIS_POLL_TIMEOUT_MS) {
            setPageState("timeout");
            return;
          }
          setPageState("analyzing");
          timer = setTimeout(() => void load(), ANALYSIS_POLL_INTERVAL_MS);
          return;
        }
        if (current.status === "REVIEW_REQUIRED" || current.status === "FAILED") {
          setForm(createReviewForm(current));
          setPageState("ready");
          return;
        }
        if (current.status === "CONFIRMED") {
          setPageState("confirmed");
          return;
        }
        setErrorMessage("검수할 수 없는 문서 상태입니다.");
        setPageState("error");
      } catch (error) {
        if (cancelled) return;
        setErrorMessage(
          error instanceof ApiError
            ? error.message
            : "분석 결과를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
        );
        setPageState("error");
      }
    }

    setPageState("loading");
    void load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [contractId, documentId, reloadKey]);

  function updatePayment(index: number, field: string, value: string) {
    setForm((current) => {
      if (!current) return current;
      const payments = [...current.payments];
      payments[index] = { ...payments[index], [field]: value };
      return { ...current, payments };
    });
  }

  function updateCancellation(index: number, summary: string) {
    setForm((current) => {
      if (!current) return current;
      const cancellationTerms = [...current.cancellationTerms];
      cancellationTerms[index] = { ...cancellationTerms[index], summary };
      return { ...current, cancellationTerms };
    });
  }

  async function handleRetryAnalysis() {
    if (documentId === undefined || isRetryingAnalysis) return;
    setIsRetryingAnalysis(true);
    setRetryErrorMessage("");
    try {
      await analyzeDocument(documentId);
      setReloadKey((key) => key + 1);
    } catch (error) {
      setRetryErrorMessage(
        error instanceof ApiError
          ? error.message
          : "분석을 다시 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setIsRetryingAnalysis(false);
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!form || isSubmitting) return;

    const errors = validateReviewForm(form);
    setValidationErrors(errors);
    if (hasReviewErrors(errors)) return;

    setIsSubmitting(true);
    setErrorMessage("");
    try {
      const contract = isEditing
        ? await updateContract(contractId, toContractConfirm(form))
        : await confirmDocument(documentId, toContractConfirm(form));
      router.push(`/contracts/${contract.id}`);
    } catch (error) {
      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : isEditing
            ? "계약을 수정하지 못했습니다. 입력값을 확인하고 다시 시도해 주세요."
            : "계약을 확정하지 못했습니다. 입력값을 확인하고 다시 시도해 주세요.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (pageState === "loading" || pageState === "analyzing") {
    return (
      <main className="content-page review-loading">
        <section className="state-card" role="status" aria-live="polite">
          <span className="progress-dot" aria-hidden="true" />
          <h1>
            {pageState === "loading" ? "문서를 확인하고 있어요" : "AI가 계약서를 분석하고 있어요"}
          </h1>
          <p>분석이 끝나면 검수 화면이 자동으로 열립니다.</p>
        </section>
      </main>
    );
  }

  if (pageState === "timeout") {
    return (
      <main className="content-page review-loading">
        <section className="state-card" role="status" aria-live="polite">
          <h1>분석이 예상보다 오래 걸리고 있어요</h1>
          <p>
            서버에서는 분석을 계속 진행하고 있으며 화면에서만 잠시 기다림을 멈췄습니다. 아래
            버튼으로 다시 확인해 주세요.
          </p>
          <button
            type="button"
            className="secondary-button"
            onClick={() => setReloadKey((key) => key + 1)}
          >
            다시 확인하기
          </button>
          <Link href="/documents/upload" className="text-link">
            나중에 확인
          </Link>
        </section>
      </main>
    );
  }

  if (pageState === "error" || pageState === "confirmed") {
    return (
      <main className="content-page">
        <section className="state-card" role={pageState === "error" ? "alert" : "status"}>
          <h1>{pageState === "confirmed" ? "이미 확정된 문서입니다" : "문서를 열지 못했습니다"}</h1>
          {pageState === "error" && <p>{errorMessage}</p>}
          {pageState === "error" && (
            <button
              type="button"
              className="secondary-button"
              onClick={() => setReloadKey((key) => key + 1)}
            >
              다시 시도
            </button>
          )}
          <Link href="/contracts" className="text-link">
            계약 목록으로
          </Link>
        </section>
      </main>
    );
  }

  if (!form || (!isEditing && !document)) return null;

  return (
    <main className="content-page review-page">
      <nav
        className="page-nav"
        aria-label={isEditing ? "계약 수정 화면 탐색" : "문서 검수 화면 탐색"}
      >
        <Link href={isEditing ? `/contracts/${contractId}` : "/documents/upload"}>
          {isEditing ? "계약 상세" : "계약서 업로드"}
        </Link>
        <span aria-hidden="true">/</span>
        <span>{isEditing ? "계약 수정" : "추출 결과 검수"}</span>
      </nav>
      <header className="page-header">
        <p className="eyebrow">{isEditing ? "EDIT CONTRACT" : "REVIEW CONTRACT"}</p>
        <h1>{isEditing ? "확정 계약을 수정합니다" : "계약 내용을 확인해 주세요"}</h1>
        <p>
          {isEditing
            ? "저장한 변경사항은 자금 현황과 AI 답변에 즉시 반영됩니다."
            : `${document?.originalName}에서 추출한 정보입니다. 원문과 다른 내용은 직접 수정해 주세요.`}
        </p>
      </header>

      {document?.status === "FAILED" && (
        <aside className="warning-panel" role="alert">
          <p>
            <strong>자동 분석에 실패했습니다.</strong>{" "}
            {document.error?.message ?? "계약서를 보며 직접 입력하거나 다시 시도해 주세요."}
          </p>
          {retryErrorMessage && <p>{retryErrorMessage}</p>}
          <button
            type="button"
            className="secondary-button"
            disabled={isRetryingAnalysis}
            onClick={() => void handleRetryAnalysis()}
          >
            {isRetryingAnalysis ? "다시 시도하는 중…" : "분석 다시 시도"}
          </button>
        </aside>
      )}
      {document?.extraction?.warnings.map((warning) => (
        <aside className="warning-panel" role="status" key={warning}>
          <strong>확인 필요</strong> {warning}
        </aside>
      ))}

      <div className="review-layout">
        <aside className="evidence-panel" aria-labelledby="evidence-title">
          <div className="sticky-panel">
            <p className="eyebrow">SOURCE EVIDENCE</p>
            <h2 id="evidence-title">계약서 근거</h2>
            <p>현재 원문 미리보기 API가 없어 AI가 보존한 근거 문장을 표시합니다.</p>
            <EvidenceList form={form} />
          </div>
        </aside>

        <form className="review-form" onSubmit={(event) => void handleSubmit(event)} noValidate>
          <section className="form-section" aria-labelledby="basic-title">
            <div className="section-heading">
              <h2 id="basic-title">기본 정보</h2>
              <span className="required-note">* 필수 입력</span>
            </div>
            <label className="field-label">
              업체명 *
              <input
                value={form.company}
                onChange={(event) => setForm({ ...form, company: event.target.value })}
                aria-invalid={Boolean(validationErrors.company)}
                aria-describedby={validationErrors.company ? "company-error" : undefined}
              />
            </label>
            {validationErrors.company && (
              <p className="field-error" id="company-error">
                {validationErrors.company}
              </p>
            )}
            <label className="field-label" htmlFor="contract-total-price">
              계약 총액 *
              <input
                id="contract-total-price"
                inputMode="numeric"
                value={form.totalPrice}
                onChange={(event) => setForm({ ...form, totalPrice: event.target.value })}
                aria-invalid={Boolean(validationErrors.totalPrice)}
                aria-describedby={validationErrors.totalPrice ? "total-price-error" : undefined}
              />
            </label>
            {/^\d+$/.test(form.totalPrice) && (
              <span className="field-hint">{formatWon(Number(form.totalPrice))}</span>
            )}
            {validationErrors.totalPrice && (
              <p className="field-error" id="total-price-error">
                {validationErrors.totalPrice}
              </p>
            )}
          </section>

          <section className="form-section" aria-labelledby="payment-title">
            <div className="section-heading">
              <div>
                <h2 id="payment-title">지급항목</h2>
                <p>확정된 미지급 금액만 자금 계획에 반영됩니다.</p>
              </div>
              <button
                type="button"
                className="secondary-button"
                onClick={() =>
                  setForm({
                    ...form,
                    payments: [
                      ...form.payments,
                      { name: "", amount: "", dueDate: "", status: "UNPAID", sourceText: null },
                    ],
                  })
                }
              >
                + 항목 추가
              </button>
            </div>
            {validationErrors.payments && (
              <p className="field-error">{validationErrors.payments}</p>
            )}
            {form.payments.map((payment, index) => (
              <fieldset className="repeatable-field" key={index}>
                <legend>지급항목 {index + 1}</legend>
                <button
                  type="button"
                  className="remove-button"
                  aria-label={`지급항목 ${index + 1} 삭제`}
                  onClick={() =>
                    setForm({
                      ...form,
                      payments: form.payments.filter((_, itemIndex) => itemIndex !== index),
                    })
                  }
                >
                  삭제
                </button>
                <div className="field-grid">
                  <label className="field-label">
                    항목명 *
                    <input
                      value={payment.name}
                      onChange={(event) => updatePayment(index, "name", event.target.value)}
                      aria-invalid={Boolean(validationErrors.paymentFields[index]?.name)}
                    />
                    {validationErrors.paymentFields[index]?.name && (
                      <span className="field-error">
                        {validationErrors.paymentFields[index].name}
                      </span>
                    )}
                  </label>
                  <label className="field-label">
                    금액 *
                    <input
                      inputMode="numeric"
                      value={payment.amount}
                      onChange={(event) => updatePayment(index, "amount", event.target.value)}
                      aria-invalid={Boolean(validationErrors.paymentFields[index]?.amount)}
                    />
                    {validationErrors.paymentFields[index]?.amount && (
                      <span className="field-error">
                        {validationErrors.paymentFields[index].amount}
                      </span>
                    )}
                  </label>
                  <label className="field-label">
                    지급일
                    <input
                      type="date"
                      value={payment.dueDate}
                      onChange={(event) => updatePayment(index, "dueDate", event.target.value)}
                    />
                  </label>
                  <label className="field-label">
                    지급 상태
                    <select
                      value={payment.status}
                      onChange={(event) =>
                        updatePayment(index, "status", event.target.value as PaymentStatus)
                      }
                    >
                      <option value="UNPAID">미지급</option>
                      <option value="PAID">지급 완료</option>
                      <option value="UNKNOWN">확인 필요</option>
                    </select>
                  </label>
                </div>
                {payment.sourceText && <p className="source-hint">근거: {payment.sourceText}</p>}
              </fieldset>
            ))}
          </section>

          <section className="form-section" aria-labelledby="cancellation-title">
            <div className="section-heading">
              <h2 id="cancellation-title">취소조건</h2>
              <button
                type="button"
                className="secondary-button"
                onClick={() =>
                  setForm({
                    ...form,
                    cancellationTerms: [
                      ...form.cancellationTerms,
                      { summary: "", sourceText: null },
                    ],
                  })
                }
              >
                + 조건 추가
              </button>
            </div>
            {form.cancellationTerms.length === 0 && (
              <p className="muted-panel">
                추출된 취소조건이 없습니다. 필요한 경우 직접 추가해 주세요.
              </p>
            )}
            {form.cancellationTerms.map((term, index) => (
              <fieldset className="repeatable-field" key={index}>
                <legend>취소조건 {index + 1}</legend>
                <button
                  type="button"
                  className="remove-button"
                  aria-label={`취소조건 ${index + 1} 삭제`}
                  onClick={() =>
                    setForm({
                      ...form,
                      cancellationTerms: form.cancellationTerms.filter(
                        (_, itemIndex) => itemIndex !== index,
                      ),
                    })
                  }
                >
                  삭제
                </button>
                <label className="field-label">
                  조건 내용 *
                  <textarea
                    rows={3}
                    value={term.summary}
                    onChange={(event) => updateCancellation(index, event.target.value)}
                    aria-invalid={Boolean(validationErrors.cancellationFields[index]?.summary)}
                  />
                  {validationErrors.cancellationFields[index]?.summary && (
                    <span className="field-error">
                      {validationErrors.cancellationFields[index].summary}
                    </span>
                  )}
                </label>
                {term.sourceText && <p className="source-hint">근거: {term.sourceText}</p>}
              </fieldset>
            ))}
          </section>

          {errorMessage && (
            <p role="alert" className="page-error">
              {errorMessage} 입력한 내용은 그대로 유지됩니다.
            </p>
          )}
          <aside className="confirmation-notice">
            {isEditing
              ? "수정된 지급 금액과 상태는 저장 즉시 자금 현황과 AI 답변에 반영됩니다."
              : "계약을 확정하기 전에는 지급 금액이 자금 현황과 AI 답변에 반영되지 않습니다."}
          </aside>
          <div className="form-actions">
            <Link href={isEditing ? `/contracts/${contractId}` : "/"} className="secondary-link">
              {isEditing ? "취소" : "나중에 확인"}
            </Link>
            <button type="submit" className="primary-button" disabled={isSubmitting}>
              {isSubmitting
                ? isEditing
                  ? "저장하는 중…"
                  : "확정하는 중…"
                : isEditing
                  ? "변경사항 저장"
                  : "계약 확정"}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}

function EvidenceList({ form }: { form: ContractReviewForm }) {
  const evidence = [
    ...form.payments.flatMap((payment) => (payment.sourceText ? [payment.sourceText] : [])),
    ...form.cancellationTerms.flatMap((term) => (term.sourceText ? [term.sourceText] : [])),
  ];
  if (evidence.length === 0) {
    return <p className="muted-panel">보존된 근거 문장이 없습니다.</p>;
  }
  return (
    <ol className="evidence-list">
      {evidence.map((source, index) => (
        <li key={`${source}-${index}`}>{source}</li>
      ))}
    </ol>
  );
}
