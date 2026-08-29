import { apiClient } from "@/shared/api/api-client";
import type { DocumentSummary } from "../model/types";

export function uploadDocument(file: File): Promise<DocumentSummary> {
  const formData = new FormData();
  formData.append("file", file);

  return apiClient<DocumentSummary>("/documents", {
    method: "POST",
    body: formData,
  });
}
