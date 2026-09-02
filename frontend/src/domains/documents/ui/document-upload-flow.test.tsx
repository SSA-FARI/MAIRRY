import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentUploadFlow } from "./document-upload-flow";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const documentId = "8f32eb5e-a2ac-44be-8ce8-393d466bc901";
const uploadUrl = "http://localhost:8000/api/documents";
const analyzeUrl = `${uploadUrl}/${documentId}/analyze`;
const uploadedDocument = {
  id: documentId,
  originalName: "contract.pdf",
  status: "UPLOADED",
};
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());
beforeEach(() => push.mockReset());

function contractFile() {
  return new File([new Uint8Array(1024)], "contract.pdf", { type: "application/pdf" });
}

describe("DocumentUploadFlow", () => {
  it("starts analysis after upload and moves to review", async () => {
    server.use(
      http.post(uploadUrl, () => HttpResponse.json(uploadedDocument, { status: 201 })),
      http.post(analyzeUrl, () =>
        HttpResponse.json({ ...uploadedDocument, status: "PROCESSING" }, { status: 202 }),
      ),
    );

    const user = userEvent.setup();
    render(<DocumentUploadFlow />);
    await user.upload(screen.getByTestId("document-upload-input"), contractFile());

    await waitFor(() => expect(push).toHaveBeenCalledWith(`/documents/${documentId}/review`));
  });

  it("allows analysis retry without uploading the file again", async () => {
    let analyzeRequests = 0;
    server.use(
      http.post(uploadUrl, () => HttpResponse.json(uploadedDocument, { status: 201 })),
      http.post(analyzeUrl, () => {
        analyzeRequests += 1;
        if (analyzeRequests === 1) {
          return HttpResponse.json(
            { error: { code: "AI_PROVIDER_ERROR", message: "분석을 시작하지 못했습니다." } },
            { status: 502 },
          );
        }
        return HttpResponse.json({ ...uploadedDocument, status: "PROCESSING" }, { status: 202 });
      }),
    );

    const user = userEvent.setup();
    render(<DocumentUploadFlow />);
    await user.upload(screen.getByTestId("document-upload-input"), contractFile());

    expect(await screen.findByRole("alert")).toHaveTextContent("분석을 시작하지 못했습니다.");
    await user.click(screen.getByRole("button", { name: "분석 다시 시도" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith(`/documents/${documentId}/review`));
    expect(analyzeRequests).toBe(2);
  });
});
