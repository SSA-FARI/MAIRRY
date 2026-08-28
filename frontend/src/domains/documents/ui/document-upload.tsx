"use client";

import { useCallback, useRef, useState } from "react";
import { ApiError } from "@/shared/api/api-client";
import { uploadDocument } from "../api/documents-api";
import {
  ALLOWED_EXTENSIONS,
  MAX_FILE_SIZE_MB,
  findUploadValidationError,
} from "../model/upload-constraints";
import type { DocumentSummary } from "../model/types";

type UploadStatus = "empty" | "uploading" | "success" | "error";

interface DocumentUploadProps {
  onUploaded?: (document: DocumentSummary) => void;
}

export function DocumentUpload({ onUploaded }: DocumentUploadProps) {
  const [status, setStatus] = useState<UploadStatus>("empty");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<DocumentSummary | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      if (status === "uploading") {
        return;
      }

      const validationError = findUploadValidationError(file);
      if (validationError) {
        setStatus("error");
        setErrorMessage(validationError);
        return;
      }

      setStatus("uploading");
      setErrorMessage(null);

      try {
        const document = await uploadDocument(file);
        setUploaded(document);
        setStatus("success");
        onUploaded?.(document);
      } catch (error) {
        setStatus("error");
        setErrorMessage(
          error instanceof ApiError
            ? error.message
            : "업로드 중 오류가 발생했습니다. 다시 시도해 주세요.",
        );
      }
    },
    [onUploaded, status],
  );

  const openFilePicker = useCallback(() => {
    if (status !== "uploading") {
      inputRef.current?.click();
    }
  }, [status]);

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragging(false);
      const file = event.dataTransfer.files[0];
      if (file) {
        void handleFile(file);
      }
    },
    [handleFile],
  );

  const handleInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) {
        void handleFile(file);
      }
      event.target.value = "";
    },
    [handleFile],
  );

  const handleReset = useCallback(() => {
    setStatus("empty");
    setErrorMessage(null);
    setUploaded(null);
  }, []);

  if (status === "success" && uploaded) {
    return (
      <section role="status" style={cardStyle} data-testid="document-upload-success">
        <p style={{ color: "var(--primary)", fontWeight: 700, marginTop: 0 }}>업로드 완료</p>
        <p style={{ margin: "4px 0" }}>{uploaded.originalName}</p>
        <p style={{ color: "var(--muted)", marginBottom: 16 }}>분석을 시작할 준비가 되었습니다.</p>
        <button type="button" onClick={handleReset} style={secondaryButtonStyle}>
          다른 파일 업로드
        </button>
      </section>
    );
  }

  return (
    <section style={cardStyle} data-testid="document-upload">
      <div
        role="button"
        tabIndex={0}
        aria-label="계약서 파일 업로드 영역"
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={openFilePicker}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openFilePicker();
          }
        }}
        style={dropZoneStyle(isDragging, status === "error")}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ALLOWED_EXTENSIONS.join(",")}
          onChange={handleInputChange}
          onClick={(event) => event.stopPropagation()}
          style={{ display: "none" }}
          aria-hidden="true"
        />
        {/* 자식이 드래그 히트테스트를 가로채 dragleave가 잘못 발생하는 걸 막는다 */}
        <div style={{ pointerEvents: "none" }}>
          {status === "uploading" ? (
            <p role="status">업로드 중입니다…</p>
          ) : (
            <>
              <p style={{ fontWeight: 600, marginTop: 0 }}>
                계약서 파일을 끌어다 놓거나 클릭해 선택하세요
              </p>
              <p style={{ color: "var(--muted)", fontSize: 14 }}>
                PDF, JPG, PNG · 최대 {MAX_FILE_SIZE_MB}MB
              </p>
            </>
          )}
        </div>
      </div>
      {status === "error" && errorMessage && (
        <p role="alert" style={{ color: "var(--danger)", marginBottom: 0 }}>
          {errorMessage}
        </p>
      )}
    </section>
  );
}

const cardStyle: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: 18,
  padding: 24,
};

function dropZoneStyle(isDragging: boolean, hasError: boolean): React.CSSProperties {
  return {
    border: `2px dashed ${hasError ? "var(--danger)" : isDragging ? "var(--primary)" : "var(--border)"}`,
    borderRadius: 12,
    padding: 32,
    textAlign: "center",
    cursor: "pointer",
    background: isDragging ? "rgba(103, 80, 229, 0.04)" : "transparent",
  };
}

const secondaryButtonStyle: React.CSSProperties = {
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: "8px 16px",
  background: "transparent",
  cursor: "pointer",
};
