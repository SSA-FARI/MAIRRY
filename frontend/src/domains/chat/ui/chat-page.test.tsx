import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { ChatPage } from "./chat-page";

const chatUrl = "http://localhost:8000/api/chat";
const contractId = "90af8db0-a099-40a0-bb92-720ec331a6a0";
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

describe("ChatPage", () => {
  it("sends a suggested question and links the returned evidence to its contract", async () => {
    let requestBody: unknown;
    server.use(
      http.post(chatUrl, async ({ request }) => {
        requestBody = await request.json();
        return HttpResponse.json({
          answer: "A웨딩홀 잔금일은 2027년 4월 30일입니다.",
          answerType: "CONTRACT",
          citations: [
            {
              contractId,
              label: "A웨딩홀 · 잔금",
              sourceText: "잔금 20,000,000원은 2027년 4월 30일까지 지급",
            },
          ],
          calculation: null,
        });
      }),
    );

    const user = userEvent.setup();
    render(<ChatPage />);
    await user.click(screen.getByRole("button", { name: "가장 가까운 잔금일은 언제야?" }));

    expect(await screen.findByText("A웨딩홀 잔금일은 2027년 4월 30일입니다.")).toBeVisible();
    expect(requestBody).toEqual({ message: "가장 가까운 잔금일은 언제야?" });
    expect(screen.getByText("잔금 20,000,000원은 2027년 4월 30일까지 지급")).toBeVisible();
    expect(screen.getByRole("link", { name: /A웨딩홀 · 잔금/ })).toHaveAttribute(
      "href",
      `/contracts/${contractId}`,
    );
  });

  it("renders calculation fields exactly as returned by the backend", async () => {
    server.use(
      http.post(chatUrl, () =>
        HttpResponse.json({
          answer: "추가 지출 후 예상 잔액은 7,000,000원입니다.",
          answerType: "CALCULATION",
          citations: [],
          calculation: {
            toolName: "simulateAdditionalExpense",
            calculatedAt: "2026-09-03T10:00:00Z",
            currentExpectedBalance: 10_000_000,
            simulatedExpectedBalance: 7_000_000,
            shortageAmount: 0,
          },
        }),
      ),
    );

    const user = userEvent.setup();
    render(<ChatPage />);
    await user.type(screen.getByLabelText("AI 플래너에게 질문하기"), "가전 300만원 추가해줘");
    await user.click(screen.getByRole("button", { name: "질문 보내기" }));

    expect(await screen.findByRole("heading", { name: "서버 계산 결과" })).toBeVisible();
    expect(screen.getByText("10,000,000원")).toBeVisible();
    expect(screen.getByText("7,000,000원")).toBeVisible();
    expect(screen.getByText("0원")).toBeVisible();
    expect(screen.getByText(/2026\. 09\. 03\./)).toHaveAttribute(
      "datetime",
      "2026-09-03T10:00:00Z",
    );
  });

  it("keeps the failed question and retries it", async () => {
    let calls = 0;
    server.use(
      http.post(chatUrl, () => {
        calls += 1;
        if (calls === 1) {
          return HttpResponse.json(
            { error: { code: "CHAT_FAILED", message: "답변 생성에 실패했습니다." } },
            { status: 500 },
          );
        }
        return HttpResponse.json({
          answer: "다시 확인했습니다.",
          answerType: "NOT_FOUND",
          citations: [],
          calculation: null,
        });
      }),
    );

    const user = userEvent.setup();
    render(<ChatPage />);
    await user.type(screen.getByLabelText("AI 플래너에게 질문하기"), "확인해줘");
    await user.click(screen.getByRole("button", { name: "질문 보내기" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("답변 생성에 실패했습니다.");
    expect(screen.getByLabelText("AI 플래너에게 질문하기")).toHaveValue("확인해줘");

    await user.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(await screen.findByText("다시 확인했습니다.")).toBeVisible();
    await waitFor(() => expect(calls).toBe(2));
  });

  it("does not allow a blank question", async () => {
    render(<ChatPage />);
    expect(screen.getByRole("button", { name: "질문 보내기" })).toBeDisabled();
  });

  it("does not submit while a Korean IME composition is active", async () => {
    let calls = 0;
    server.use(
      http.post(chatUrl, () => {
        calls += 1;
        return HttpResponse.json({
          answer: "확인했습니다.",
          answerType: "NOT_FOUND",
          citations: [],
          calculation: null,
        });
      }),
    );

    const user = userEvent.setup();
    render(<ChatPage />);
    const input = screen.getByLabelText("AI 플래너에게 질문하기");
    await user.type(input, "잔금일");
    fireEvent.keyDown(input, { key: "Enter", isComposing: true });
    expect(calls).toBe(0);
    expect(input).toHaveValue("잔금일");

    fireEvent.keyDown(input, { key: "Enter", isComposing: false });
    await waitFor(() => expect(calls).toBe(1));
  });
});
