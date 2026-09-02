import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { ContractDetailPage } from "./contract-detail-page";
import { ContractListPage } from "./contract-list-page";

const contractId = "90af8db0-a099-40a0-bb92-720ec331a6a0";
const listUrl = "http://localhost:8000/api/contracts";
const detailUrl = `${listUrl}/${contractId}`;
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

describe("contract pages", () => {
  it("shows an actionable empty contract list", async () => {
    server.use(http.get(listUrl, () => HttpResponse.json({ items: [] })));

    render(<ContractListPage />);

    expect(
      await screen.findByRole("heading", { name: "아직 확정된 계약이 없습니다" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "첫 계약서 등록" })).toHaveAttribute(
      "href",
      "/documents/upload",
    );
  });

  it("shows contract summary and next payment in the list", async () => {
    server.use(
      http.get(listUrl, () =>
        HttpResponse.json({
          items: [
            {
              id: contractId,
              company: "A웨딩홀",
              totalPrice: 23_000_000,
              status: "CONFIRMED",
              nextPayment: {
                contractId,
                company: "A웨딩홀",
                name: "잔금",
                amount: 20_000_000,
                dueDate: "2027-04-30",
              },
            },
          ],
        }),
      ),
    );

    render(<ContractListPage />);

    expect(await screen.findByRole("heading", { name: "A웨딩홀" })).toBeVisible();
    expect(screen.getByText("2027.04.30 · 잔금")).toBeVisible();
    expect(screen.getByRole("link", { name: "계약 상세 보기 →" })).toHaveAttribute(
      "href",
      `/contracts/${contractId}`,
    );
  });

  it("shows payments, cancellation terms, and preserved evidence", async () => {
    server.use(
      http.get(detailUrl, () =>
        HttpResponse.json({
          id: contractId,
          documentId: "8f32eb5e-a2ac-44be-8ce8-393d466bc901",
          documentType: "WEDDING_HALL",
          company: "A웨딩홀",
          totalPrice: 23_000_000,
          status: "CONFIRMED",
          payments: [
            {
              name: "잔금",
              amount: 20_000_000,
              dueDate: "2027-04-30",
              status: "UNPAID",
              sourceText: "잔금은 4월 30일까지",
            },
          ],
          cancellationTerms: [
            {
              summary: "90일 전 전액 환급",
              sourceText: "예식일 90일 전까지 취소 시 전액 환급",
            },
          ],
        }),
      ),
    );

    render(<ContractDetailPage contractId={contractId} />);

    expect(await screen.findByRole("heading", { name: "A웨딩홀" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "잔금" })).toBeVisible();
    expect(screen.getByText("잔금은 4월 30일까지")).toBeVisible();
    expect(screen.getByRole("heading", { name: "90일 전 전액 환급" })).toBeVisible();
    expect(screen.getByText("예식일 90일 전까지 취소 시 전액 환급")).toBeVisible();
  });
});
