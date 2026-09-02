import { apiClient } from "@/shared/api/api-client";
import type { DocumentDetail, DocumentSummary } from "../model/types";

export function uploadDocument(file: File): Promise<DocumentSummary> {
  const formData = new FormData();
  formData.append("file", file);

  return apiClient<DocumentSummary>("/documents", {
    method: "POST",
    body: formData,
  });
}

export function getDocument(documentId: string): Promise<DocumentDetail> {
  return apiClient<DocumentDetail>(`/documents/${documentId}`);
}

export function analyzeDocument(documentId: string): Promise<DocumentDetail> {
  return apiClient<DocumentDetail>(`/documents/${documentId}/analyze`, { method: "POST" });
}
