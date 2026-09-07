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
afterEach(() => {
  server.resetHandlers();
  window.localStorage.clear();
});

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

  it("renders a RAG citation with source type and page without a fake link", async () => {
    server.use(
      http.post(chatUrl, () =>
        HttpResponse.json({
          answer: "계약서의 취소 조항을 확인했습니다.",
          answerType: "RAG",
          usedRag: true,
          citations: [
            {
              contractId: null,
              documentId: null,
              sourceType: "DOMAIN_KNOWLEDGE",
              title: "웨딩 계약 용어 안내",
              clauseTitle: "위약금과 환불 규정",
              page: 3,
              label: "웨딩 계약 용어 안내 · 위약금과 환불 규정",
              sourceText: "환불 가능 여부는 실제 계약 조항을 확인해야 합니다.",
            },
          ],
          calculation: null,
        }),
      ),
    );

    const user = userEvent.setup();
    render(<ChatPage />);
    await user.type(screen.getByLabelText("AI 플래너에게 질문하기"), "위약금이 뭐야?");
    await user.click(screen.getByRole("button", { name: "질문 보내기" }));

    expect(await screen.findByText("DOMAIN_KNOWLEDGE · 3페이지")).toBeVisible();
    expect(screen.queryByRole("link", { name: /웨딩 계약 용어 안내/ })).not.toBeInTheDocument();
  });

  it("keeps the failed question and retries it", async () => {
    let calls = 0;
    const requestBodies: unknown[] = [];
    window.localStorage.setItem("mairry.chat.conversationId", "conversation-existing");
    server.use(
      http.post(chatUrl, async ({ request }) => {
        calls += 1;
        requestBodies.push(await request.json());
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
    expect(requestBodies).toEqual([
      { conversationId: "conversation-existing", message: "확인해줘" },
      { conversationId: "conversation-existing", message: "확인해줘" },
    ]);
  });

  it("reuses the returned conversation id for the next question", async () => {
    const requestBodies: unknown[] = [];
    server.use(
      http.post(chatUrl, async ({ request }) => {
        requestBodies.push(await request.json());
        return HttpResponse.json({
          conversationId: "conversation-1",
          messageId: `message-${requestBodies.length}`,
          answer: `답변 ${requestBodies.length}`,
          answerType: "CONTRACT",
          citations: [],
          calculation: null,
        });
      }),
    );

    const user = userEvent.setup();
    render(<ChatPage />);
    const input = screen.getByLabelText("AI 플래너에게 질문하기");
    await user.type(input, "첫 질문");
    await user.click(screen.getByRole("button", { name: "질문 보내기" }));
    expect(await screen.findByText("답변 1")).toBeVisible();
    await user.type(input, "후속 질문");
    await user.click(screen.getByRole("button", { name: "질문 보내기" }));
    expect(await screen.findByText("답변 2")).toBeVisible();

    expect(requestBodies).toEqual([
      { message: "첫 질문" },
      { conversationId: "conversation-1", message: "후속 질문" },
    ]);
    expect(window.localStorage.getItem("mairry.chat.conversationId")).toBe("conversation-1");
  });

  it("restores a conversation id after refresh and clears it for a new conversation", async () => {
    const requestBodies: unknown[] = [];
    window.localStorage.setItem("mairry.chat.conversationId", "conversation-restored");
    server.use(
      http.post(chatUrl, async ({ request }) => {
        requestBodies.push(await request.json());
        return HttpResponse.json({
          conversationId: "conversation-new",
          messageId: "message-new",
          answer: "확인했습니다.",
          answerType: "NOT_FOUND",
          citations: [],
          calculation: null,
        });
      }),
    );

    const user = userEvent.setup();
    render(<ChatPage />);
    await user.click(screen.getByRole("button", { name: "새 대화" }));
    expect(window.localStorage.getItem("mairry.chat.conversationId")).toBeNull();
    await user.type(screen.getByLabelText("AI 플래너에게 질문하기"), "새 질문");
    await user.click(screen.getByRole("button", { name: "질문 보내기" }));
    await screen.findByText("확인했습니다.");

    expect(requestBodies).toEqual([{ message: "새 질문" }]);
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
