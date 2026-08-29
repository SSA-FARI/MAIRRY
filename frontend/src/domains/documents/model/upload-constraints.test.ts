import { describe, expect, it } from "vitest";
import { MAX_FILE_SIZE_BYTES, findUploadValidationError } from "./upload-constraints";

function makeFile(name: string, size: number): File {
  return new File([new Uint8Array(size)], name);
}

describe("findUploadValidationError", () => {
  it("accepts an allowed extension within the size limit", () => {
    expect(findUploadValidationError(makeFile("contract.pdf", 1024))).toBeNull();
  });

  it("rejects a disallowed extension", () => {
    expect(findUploadValidationError(makeFile("contract.txt", 1024))).toBe(
      "PDF, JPG, PNG 파일만 업로드할 수 있습니다.",
    );
  });

  it("rejects an empty (0-byte) file", () => {
    expect(findUploadValidationError(makeFile("contract.pdf", 0))).toBe(
      "빈 파일은 업로드할 수 없습니다.",
    );
  });

  it("rejects a file over the size limit", () => {
    expect(findUploadValidationError(makeFile("contract.pdf", MAX_FILE_SIZE_BYTES + 1))).toBe(
      "파일 용량은 10MB 이하여야 합니다.",
    );
  });
});
