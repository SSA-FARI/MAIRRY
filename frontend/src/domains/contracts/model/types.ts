import type { DocumentType, PaymentStatus } from "@/domains/documents";

export interface ConfirmedPaymentInput {
  name: string;
  amount: number;
  dueDate: string | null;
  status: PaymentStatus;
  sourceText: string | null;
}

export interface ConfirmedPayment extends ConfirmedPaymentInput {
  id: string;
}

export interface ConfirmedCancellationTerm {
  summary: string;
  sourceText: string | null;
}

export interface ContractConfirm {
  documentType: DocumentType;
  company: string;
  totalPrice: number;
  payments: ConfirmedPaymentInput[];
  cancellationTerms: ConfirmedCancellationTerm[];
}

export interface UpcomingPayment {
  contractId: string;
  company: string;
  name: string;
  amount: number;
  dueDate: string;
}

export interface ContractSummary {
  id: string;
  company: string;
  totalPrice: number;
  status: "CONFIRMED";
  nextPayment: UpcomingPayment | null;
}

export interface ContractList {
  items: ContractSummary[];
}

export interface ContractDetail extends Omit<ContractConfirm, "payments"> {
  id: string;
  documentId: string;
  status: "CONFIRMED";
  payments: ConfirmedPayment[];
}
