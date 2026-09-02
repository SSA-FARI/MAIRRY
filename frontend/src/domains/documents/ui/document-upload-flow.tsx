"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError } from "@/shared/api/api-client";
import { analyzeDocument } from "../api/documents-api";
import type { DocumentSummary } from "../model/types";
import { DocumentUpload } from "./document-upload";

export function DocumentUploadFlow() {
  const router = useRouter();
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [pendingDocument, setPendingDocument] = useState<DocumentSummary | null>(null);
  const [isStartingAnalysis, setIsStartingAnalysis] = useState(false);

  async function startAnalysis(document: DocumentSummary) {
    setAnalysisError(null);
    setIsStartingAnalysis(true);
    try {
      await analyzeDocument(document.id);
      router.push(`/documents/${document.id}/review`);
    } catch (error) {
      setAnalysisError(
        error instanceof ApiError
          ? error.message
          : "분석을 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
    } finally {
      setIsStartingAnalysis(false);
    }
  }

  function handleUploaded(document: DocumentSummary) {
    setPendingDocument(document);
    void startAnalysis(document);
  }

  return (
    <>
      <DocumentUpload onUploaded={handleUploaded} />
      {analysisError && (
        <div role="alert" className="page-error">
          <p>{analysisError}</p>
          {pendingDocument && (
            <button
              type="button"
              className="secondary-button"
              disabled={isStartingAnalysis}
              onClick={() => void startAnalysis(pendingDocument)}
            >
              {isStartingAnalysis ? "다시 시작하는 중…" : "분석 다시 시도"}
            </button>
          )}
        </div>
      )}
    </>
  );
}
