export type DocumentStatus = "UPLOADED" | "PROCESSING" | "REVIEW_REQUIRED" | "FAILED" | "CONFIRMED";

export interface DocumentSummary {
  id: string;
  originalName: string;
  status: DocumentStatus;
}

export type AnalysisSource = "LIVE_AI" | "DEMO_FALLBACK";
export type DocumentType = "WEDDING_HALL" | "UNKNOWN";
export type PaymentStatus = "PAID" | "UNPAID" | "UNKNOWN";

export interface ExtractedPayment {
  name: string;
  amount: number | null;
  dueDate: string | null;
  status: PaymentStatus;
  sourceText: string;
}

export interface ExtractedCancellationTerm {
  summary: string;
  sourceText: string;
}

export interface DocumentExtraction {
  documentType: DocumentType;
  company: string | null;
  totalPrice: number | null;
  payments: ExtractedPayment[];
  cancellationTerms: ExtractedCancellationTerm[];
  warnings: string[];
}

export interface DocumentDetail extends DocumentSummary {
  analysisSource: AnalysisSource | null;
  extraction: DocumentExtraction | null;
  error: { code: string; message: string; details: Record<string, unknown> } | null;
}

export interface DocumentPreviewUrl {
  url: string;
  expiresAt: string;
}
