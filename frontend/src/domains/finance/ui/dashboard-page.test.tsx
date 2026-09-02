import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { DashboardPage } from "./dashboard-page";

vi.mock("@/domains/auth", () => ({
  useDemoSession: () => ({ session: { mode: "DEMO", user: { displayName: "마리" } } }),
}));

const baseUrl = "http://localhost:8000/api";
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

const plan = { id: "plan-1", weddingDate: "2027-05-15", availableAsset: 30_000_000 };
const summary = {
  availableAsset: 35_000_000,
  remainingExpense: 20_000_000,
  expectedBalance: 15_000_000,
  nearestPayment: {
    contractId: "contract-1",
    company: "A웨딩홀",
    name: "잔금",
    amount: 20_000_000,
    dueDate: "2027-04-30",
  },
  timeline: [
    {
      contractId: "contract-1",
      company: "A웨딩홀",
      name: "잔금",
      amount: 20_000_000,
      dueDate: "2027-04-30",
    },
  ],
};

describe("DashboardPage", () => {
  it("renders backend wedding plan and finance summary without mock constants", async () => {
    server.use(
      http.get(`${baseUrl}/wedding-plan`, () => HttpResponse.json(plan)),
      http.get(`${baseUrl}/finance/summary`, () => HttpResponse.json(summary)),
    );
    render(<DashboardPage />);
    expect(await screen.findByText("5월 15일 결혼식", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("35,000,000원")).toBeInTheDocument();
    expect(screen.getAllByText("20,000,000원").length).toBeGreaterThan(0);
    expect(screen.getAllByText("15,000,000원").length).toBeGreaterThan(0);
    expect(screen.getByText("A웨딩홀 · 잔금")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "지급 일정 캘린더" })).toBeInTheDocument();
  });

  it("shows setup on plan 404 and sends only the contract fields", async () => {
    let body: unknown;
    server.use(
      http.get(`${baseUrl}/wedding-plan`, () =>
        HttpResponse.json(
          { error: { code: "RESOURCE_NOT_FOUND", message: "없음" } },
          { status: 404 },
        ),
      ),
      http.put(`${baseUrl}/wedding-plan`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(plan);
      }),
      http.get(`${baseUrl}/finance/summary`, () => HttpResponse.json(summary)),
    );
    const user = userEvent.setup();
    render(<DashboardPage />);
    expect(
      await screen.findByRole("heading", { name: "결혼 준비를 시작해볼까요?" }),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText("결혼 예정일"), "2027-05-15");
    await user.type(screen.getByLabelText("현재 준비된 공동 현금 자산"), "30000000");
    await user.click(screen.getByRole("button", { name: "계획 시작하기" }));
    await waitFor(() =>
      expect(body).toEqual({ weddingDate: "2027-05-15", availableAsset: 30_000_000 }),
    );
    expect((body as Record<string, unknown>).userId).toBeUndefined();
    expect(await screen.findByText("총 자산")).toBeInTheDocument();
  });

  it("calls simulation once and renders the backend result", async () => {
    let calls = 0;
    let body: unknown;
    server.use(
      http.get(`${baseUrl}/wedding-plan`, () => HttpResponse.json(plan)),
      http.get(`${baseUrl}/finance/summary`, () => HttpResponse.json(summary)),
      http.post(`${baseUrl}/finance/simulate`, async ({ request }) => {
        calls += 1;
        body = await request.json();
        return HttpResponse.json({
          currentExpectedBalance: 15_000_000,
          simulatedExpectedBalance: -2_000_000,
          shortageAmount: 2_000_000,
        });
      }),
    );
    const user = userEvent.setup();
    render(<DashboardPage />);
    await screen.findByRole("heading", { name: "지급 일정 캘린더" });
    await user.click(screen.getByRole("button", { name: "추가 지출 계산" }));
    expect(screen.getByRole("dialog", { name: "추가 지출 시뮬레이션" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("추가 지출 항목"), "가전 비용");
    await user.type(screen.getByLabelText("추가로 예상되는 지출"), "17000000");
    await user.click(screen.getByRole("button", { name: /계산하기/ }));
    expect((await screen.findAllByText("-2,000,000원")).length).toBeGreaterThan(0);
    expect(screen.getByText("⚠ 부족 2,000,000원")).toBeInTheDocument();
    expect(calls).toBe(1);
    expect(body).toEqual({ name: "가전 비용", amount: 17_000_000 });
  });

  it("selects a real payment date in the calendar and exposes its detail", async () => {
    server.use(
      http.get(`${baseUrl}/wedding-plan`, () => HttpResponse.json(plan)),
      http.get(`${baseUrl}/finance/summary`, () => HttpResponse.json(summary)),
    );
    const user = userEvent.setup();
    render(<DashboardPage />);
    const paymentDate = await screen.findByRole("gridcell", {
      name: /2027-04-30, 지급 예정 1건/,
    });
    await user.click(paymentDate);
    expect(paymentDate).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("2027.04.30")).toBeInTheDocument();
    expect(screen.getAllByText("잔금 · 20,000,000원").length).toBeGreaterThan(0);
  });

  it("initially selects the oldest overdue payment before the nearest future payment", async () => {
    const overdueSummary = {
      ...summary,
      timeline: [
        {
          contractId: "contract-newer-overdue",
          company: "두 번째 업체",
          name: "잔금",
          amount: 2_000_000,
          dueDate: "2020-02-10",
        },
        {
          contractId: "contract-oldest-overdue",
          company: "가장 오래된 업체",
          name: "계약금",
          amount: 1_000_000,
          dueDate: "2020-01-05",
        },
      ],
    };
    server.use(
      http.get(`${baseUrl}/wedding-plan`, () => HttpResponse.json(plan)),
      http.get(`${baseUrl}/finance/summary`, () => HttpResponse.json(overdueSummary)),
    );
    render(<DashboardPage />);
    const oldestDate = await screen.findByRole("gridcell", {
      name: /2020-01-05, 연체 1건/,
    });
    expect(oldestDate).toHaveAttribute("aria-selected", "true");
    expect(screen.getAllByText("가장 오래된 업체").length).toBeGreaterThan(0);
  });
});
