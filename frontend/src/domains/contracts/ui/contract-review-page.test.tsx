import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ContractEditPage, ContractReviewPage } from "./contract-review-page";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const documentId = "8f32eb5e-a2ac-44be-8ce8-393d466bc901";
const contractId = "90af8db0-a099-40a0-bb92-720ec331a6a0";
const documentUrl = `http://localhost:8000/api/documents/${documentId}`;
const confirmUrl = `${documentUrl}/confirm`;
const contractUrl = `http://localhost:8000/api/contracts/${contractId}`;
const documentResponse = {
  id: documentId,
  originalName: "hall.pdf",
  status: "REVIEW_REQUIRED",
  analysisSource: "DEMO_FALLBACK",
  extraction: {
    documentType: "WEDDING_HALL",
    company: "A웨딩홀",
    totalPrice: 23_000_000,
    payments: [
      {
        name: "잔금",
        amount: 20_000_000,
        dueDate: "2027-04-30",
        status: "UNPAID",
        sourceText: "잔금 20,000,000원은 2027년 4월 30일까지",
      },
    ],
    cancellationTerms: [],
    warnings: ["총액과 지급항목 합계를 확인해 주세요."],
  },
  error: null,
};

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());
beforeEach(() => push.mockReset());

describe("ContractReviewPage", () => {
  it("shows extraction values, evidence, and warnings", async () => {
    server.use(http.get(documentUrl, () => HttpResponse.json(documentResponse)));

    render(<ContractReviewPage documentId={documentId} />);

    expect(await screen.findByRole("heading", { name: "계약 내용을 확인해 주세요" })).toBeVisible();
    expect(screen.getByLabelText("업체명 *")).toHaveValue("A웨딩홀");
    expect(screen.getByLabelText("계약 총액 *")).toHaveValue("23000000");
    expect(screen.getByText("잔금 20,000,000원은 2027년 4월 30일까지")).toBeVisible();
    expect(screen.getByText(/근거: 잔금 20,000,000원은 2027년 4월 30일까지/)).toBeVisible();
    expect(screen.getByText("총액과 지급항목 합계를 확인해 주세요.")).toBeVisible();
  });

  it("submits edited values and moves to the confirmed contract", async () => {
    let receivedBody: unknown;
    server.use(
      http.get(documentUrl, () => HttpResponse.json(documentResponse)),
      http.put(confirmUrl, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json({
          id: contractId,
          documentId,
          documentType: "WEDDING_HALL",
          company: "수정 웨딩홀",
          totalPrice: 23_000_000,
          status: "CONFIRMED",
          payments: documentResponse.extraction.payments,
          cancellationTerms: [],
        });
      }),
    );

    const user = userEvent.setup();
    render(<ContractReviewPage documentId={documentId} />);
    const company = await screen.findByLabelText("업체명 *");
    await user.clear(company);
    await user.type(company, "수정 웨딩홀");
    await user.click(screen.getByRole("button", { name: "계약 확정" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith(`/contracts/${contractId}`));
    expect(receivedBody).toMatchObject({
      company: "수정 웨딩홀",
      totalPrice: 23_000_000,
      payments: [{ name: "잔금", amount: 20_000_000 }],
    });
  });

  it("keeps edited inputs when confirmation fails", async () => {
    server.use(
      http.get(documentUrl, () => HttpResponse.json(documentResponse)),
      http.put(confirmUrl, () =>
        HttpResponse.json(
          { error: { code: "INVALID_STATE", message: "이미 확정된 문서입니다." } },
          { status: 409 },
        ),
      ),
    );

    const user = userEvent.setup();
    render(<ContractReviewPage documentId={documentId} />);
    const company = await screen.findByLabelText("업체명 *");
    await user.clear(company);
    await user.type(company, "입력 유지 웨딩홀");
    await user.click(screen.getByRole("button", { name: "계약 확정" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("이미 확정된 문서입니다.");
    expect(company).toHaveValue("입력 유지 웨딩홀");
  });
});

describe("ContractEditPage", () => {
  it("loads confirmed values, updates them, and returns to detail", async () => {
    let receivedBody: unknown;
    const contract = {
      id: contractId,
      documentId,
      documentType: "WEDDING_HALL",
      company: "A웨딩홀",
      totalPrice: 23_000_000,
      status: "CONFIRMED",
      payments: documentResponse.extraction.payments,
      cancellationTerms: [],
    };
    server.use(
      http.get(contractUrl, () => HttpResponse.json(contract)),
      http.put(contractUrl, async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json({ ...contract, company: "수정 웨딩홀" });
      }),
    );

    const user = userEvent.setup();
    render(<ContractEditPage contractId={contractId} />);
    const company = await screen.findByLabelText("업체명 *");
    await user.clear(company);
    await user.type(company, "수정 웨딩홀");
    await user.click(screen.getByRole("button", { name: "변경사항 저장" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith(`/contracts/${contractId}`));
    expect(receivedBody).toMatchObject({ company: "수정 웨딩홀" });
  });
});
