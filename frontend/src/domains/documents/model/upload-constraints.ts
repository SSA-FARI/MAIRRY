// backend/app/core/config.py의 max_upload_size_bytes 기본값과 동일해야 한다 (docs/07_API_SPEC.md).
export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
export const MAX_FILE_SIZE_MB = MAX_FILE_SIZE_BYTES / (1024 * 1024);

export const ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"];

export function findUploadValidationError(file: File): string | null {
  const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return "PDF, JPG, PNG 파일만 업로드할 수 있습니다.";
  }
  if (file.size === 0) {
    return "빈 파일은 업로드할 수 없습니다.";
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `파일 용량은 ${MAX_FILE_SIZE_MB}MB 이하여야 합니다.`;
  }
  return null;
}
