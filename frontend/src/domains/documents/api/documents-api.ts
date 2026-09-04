import { apiClient } from "@/shared/api/api-client";
import type { DocumentDetail, DocumentPreviewUrl, DocumentSummary } from "../model/types";

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

/** 매 호출마다 새 서명 URL이 발급되므로 (07_API_SPEC.md) 응답을 캐시하지 말고 표시 직전에 호출한다. */
export function getDocumentPreviewUrl(documentId: string): Promise<DocumentPreviewUrl> {
  return apiClient<DocumentPreviewUrl>(`/documents/${documentId}/preview-url`);
}
