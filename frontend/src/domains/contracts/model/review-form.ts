import type { DocumentDetail, DocumentType, PaymentStatus } from "@/domains/documents";
import type { ContractConfirm } from "./types";

export interface ReviewPaymentInput {
  name: string;
  amount: string;
  dueDate: string;
  status: PaymentStatus;
  sourceText: string | null;
}

export interface ReviewCancellationInput {
  summary: string;
  sourceText: string | null;
}

export interface ContractReviewForm {
  documentType: DocumentType;
  company: string;
  totalPrice: string;
  payments: ReviewPaymentInput[];
  cancellationTerms: ReviewCancellationInput[];
}

export interface ReviewValidationErrors {
  company?: string;
  totalPrice?: string;
  payments?: string;
  paymentFields: Record<number, { name?: string; amount?: string }>;
  cancellationFields: Record<number, { summary?: string }>;
}

export function createReviewForm(document: DocumentDetail): ContractReviewForm {
  const extraction = document.extraction;
  return {
    documentType: extraction?.documentType ?? "WEDDING_HALL",
    company: extraction?.company ?? "",
    totalPrice: extraction?.totalPrice?.toString() ?? "",
    payments:
      extraction?.payments.map((payment) => ({
        name: payment.name,
        amount: payment.amount?.toString() ?? "",
        dueDate: payment.dueDate ?? "",
        status: payment.status,
        sourceText: payment.sourceText || null,
      })) ?? [],
    cancellationTerms:
      extraction?.cancellationTerms.map((term) => ({
        summary: term.summary,
        sourceText: term.sourceText || null,
      })) ?? [],
  };
}

function parseWon(value: string): number | null {
  if (!/^\d+$/.test(value.trim())) {
    return null;
  }
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

export function validateReviewForm(form: ContractReviewForm): ReviewValidationErrors {
  const errors: ReviewValidationErrors = { paymentFields: {}, cancellationFields: {} };

  if (!form.company.trim()) {
    errors.company = "업체명을 입력해 주세요.";
  }
  if (parseWon(form.totalPrice) === null) {
    errors.totalPrice = "총액은 0 이상의 정수로 입력해 주세요.";
  }
  if (form.payments.length === 0) {
    errors.payments = "지급항목을 한 개 이상 입력해 주세요.";
  }

  form.payments.forEach((payment, index) => {
    const fieldErrors: { name?: string; amount?: string } = {};
    if (!payment.name.trim()) {
      fieldErrors.name = "항목명을 입력해 주세요.";
    }
    if (parseWon(payment.amount) === null) {
      fieldErrors.amount = "금액은 0 이상의 정수로 입력해 주세요.";
    }
    if (Object.keys(fieldErrors).length > 0) {
      errors.paymentFields[index] = fieldErrors;
    }
  });

  form.cancellationTerms.forEach((term, index) => {
    if (!term.summary.trim()) {
      errors.cancellationFields[index] = { summary: "취소조건 내용을 입력해 주세요." };
    }
  });

  return errors;
}

export function hasReviewErrors(errors: ReviewValidationErrors): boolean {
  return Boolean(
    errors.company ||
    errors.totalPrice ||
    errors.payments ||
    Object.keys(errors.paymentFields).length ||
    Object.keys(errors.cancellationFields).length,
  );
}

export function toContractConfirm(form: ContractReviewForm): ContractConfirm {
  return {
    documentType: form.documentType,
    company: form.company.trim(),
    totalPrice: Number(form.totalPrice),
    payments: form.payments.map((payment) => ({
      name: payment.name.trim(),
      amount: Number(payment.amount),
      dueDate: payment.dueDate || null,
      status: payment.status,
      sourceText: payment.sourceText,
    })),
    cancellationTerms: form.cancellationTerms.map((term) => ({
      summary: term.summary.trim(),
      sourceText: term.sourceText,
    })),
  };
}
