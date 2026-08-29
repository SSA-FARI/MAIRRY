import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { DocumentUpload } from "./document-upload";

const uploadUrl = "http://localhost:8000/api/documents";
const uploadedDocument = {
  id: "8f32eb5e-a2ac-44be-8ce8-393d466bc901",
  originalName: "contract.pdf",
  status: "UPLOADED" as const,
};

function makeFile(name: string, size: number, type: string): File {
  return new File([new Uint8Array(size)], name, { type });
}

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

describe("DocumentUpload", () => {
  it("shows the empty state with format and size guidance", () => {
    render(<DocumentUpload />);

    expect(screen.getByText("계약서 파일을 끌어다 놓거나 클릭해 선택하세요")).toBeVisible();
    expect(screen.getByText("PDF, JPG, PNG · 최대 10MB")).toBeVisible();
  });

  it("rejects a disallowed extension dropped onto the dropzone, without calling the API", async () => {
    // 드래그 앤 드롭은 <input accept>과 달리 브라우저가 확장자를 걸러주지 않으므로,
    // 이 경로의 클라이언트 검증을 실제로 확인하려면 드롭 이벤트로 시뮬레이션해야 한다.
    let requestCount = 0;
    server.use(
      http.post(uploadUrl, () => {
        requestCount += 1;
        return HttpResponse.json(uploadedDocument, { status: 201 });
      }),
    );

    render(<DocumentUpload />);

    fireEvent.drop(screen.getByRole("button", { name: "계약서 파일 업로드 영역" }), {
      dataTransfer: { files: [makeFile("notes.txt", 1024, "text/plain")] },
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "PDF, JPG, PNG 파일만 업로드할 수 있습니다.",
    );
    expect(requestCount).toBe(0);
  });

  it("uploads a valid file and shows the success state", async () => {
    const onUploaded = vi.fn();
    server.use(http.post(uploadUrl, () => HttpResponse.json(uploadedDocument, { status: 201 })));

    const user = userEvent.setup();
    render(<DocumentUpload onUploaded={onUploaded} />);

    await user.upload(
      screen.getByTestId("document-upload-input"),
      makeFile("contract.pdf", 1024, "application/pdf"),
    );

    expect(await screen.findByTestId("document-upload-success")).toHaveTextContent("contract.pdf");
    expect(onUploaded).toHaveBeenCalledWith(uploadedDocument);
  });

  it("shows the backend's error message when the upload fails", async () => {
    server.use(
      http.post(uploadUrl, () =>
        HttpResponse.json(
          { error: { code: "STORAGE_ERROR", message: "파일을 저장하지 못했습니다." } },
          { status: 502 },
        ),
      ),
    );

    const user = userEvent.setup();
    render(<DocumentUpload />);

    await user.upload(
      screen.getByTestId("document-upload-input"),
      makeFile("contract.pdf", 1024, "application/pdf"),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("파일을 저장하지 못했습니다.");
  });

  it("ignores a second file selected while the first upload is still in flight", async () => {
    let requestCount = 0;
    let resolveRequest: (() => void) | undefined;
    const requestGate = new Promise<void>((resolve) => {
      resolveRequest = resolve;
    });

    server.use(
      http.post(uploadUrl, async () => {
        requestCount += 1;
        await requestGate;
        return HttpResponse.json(uploadedDocument, { status: 201 });
      }),
    );

    const user = userEvent.setup();
    render(<DocumentUpload />);
    const input = screen.getByTestId("document-upload-input");

    await user.upload(input, makeFile("contract.pdf", 1024, "application/pdf"));
    expect(await screen.findByRole("status")).toHaveTextContent("업로드 중입니다");

    await user.upload(input, makeFile("second.pdf", 1024, "application/pdf"));
    expect(requestCount).toBe(1);

    await act(async () => resolveRequest?.());
    await waitFor(() => expect(screen.getByTestId("document-upload-success")).toBeVisible());
  });
});
