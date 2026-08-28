export type DocumentStatus = "UPLOADED" | "PROCESSING" | "REVIEW_REQUIRED" | "FAILED" | "CONFIRMED";

export interface DocumentSummary {
  id: string;
  originalName: string;
  status: DocumentStatus;
}
