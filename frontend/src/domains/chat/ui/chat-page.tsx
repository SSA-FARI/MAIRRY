"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "@/shared/api/api-client";
import { formatWon } from "@/shared/lib/money";
import { sendChatMessage } from "../api/chat-api";
import type {
  ChatMessage,
  ChatResponse,
  FinanceCalculation,
  SimulationCalculation,
} from "../model/types";

const SUGGESTED_QUESTIONS = [
  "가장 가까운 잔금일은 언제야?",
  "남은 금액과 예상 잔액 알려줘",
  "가전 비용 300만 원을 추가하면 괜찮아?",
  "웨딩홀 취소 조건 알려줘",
] as const;

const INITIAL_MESSAGE: ChatMessage = {
  id: 0,
  role: "assistant",
  text: "확정된 계약과 현재 자금 현황을 근거로 답해드릴게요. 무엇이 궁금한가요?",
};

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.message) return error.message;
  return "답변을 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

function formatCalculatedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [failedQuestion, setFailedQuestion] = useState<string | null>(null);
  const nextId = useRef(1);
  const controller = useRef<AbortController | null>(null);
  const conversationEnd = useRef<HTMLDivElement | null>(null);

  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (typeof conversationEnd.current?.scrollIntoView === "function") {
      conversationEnd.current.scrollIntoView({ block: "nearest" });
    }
  }, [messages, sending]);

  async function ask(question: string, appendUserMessage = true) {
    const normalized = question.trim();
    if (!normalized || sending) return;

    controller.current?.abort();
    const userMessage: ChatMessage = { id: nextId.current++, role: "user", text: normalized };
    if (appendUserMessage) setMessages((current) => [...current, userMessage]);
    setInput("");
    setError(null);
    setFailedQuestion(null);
    setSending(true);
    const requestController = new AbortController();
    controller.current = requestController;

    try {
      const response = await sendChatMessage(normalized, requestController.signal);
      setMessages((current) => [
        ...current,
        { id: nextId.current++, role: "assistant", text: response.answer, response },
      ]);
    } catch (requestError) {
      if (requestController.signal.aborted) return;
      setError(errorMessage(requestError));
      setFailedQuestion(normalized);
      setInput(normalized);
    } finally {
      if (!requestController.signal.aborted) setSending(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void ask(input);
  }

  return (
    <div className="chat-shell">
      <header className="chat-header">
        <Link className="chat-logo" href="/">
          MAIRRY
        </Link>
        <nav aria-label="주요 메뉴">
          <Link href="/">금융 대시보드</Link>
          <Link href="/contracts">계약 관리</Link>
          <Link href="/documents/upload">계약서 업로드</Link>
          <Link className="active" href="/chat" aria-current="page">
            AI 질문
          </Link>
        </nav>
        <span className="chat-demo-badge">DEMO</span>
      </header>

      <main className="chat-main">
        <section className="chat-intro" aria-labelledby="chat-title">
          <div>
            <span className="chat-eyebrow">GROUNDED WEDDING ASSISTANT</span>
            <h1 id="chat-title">계약과 자금, 바로 물어보세요</h1>
          </div>
          <p>
            확정된 계약 원문과 서버 계산 결과만 사용합니다.
            <br />
            답변의 근거도 함께 확인할 수 있어요.
          </p>
        </section>

        <div className="chat-layout">
          <section className="chat-conversation" aria-label="AI 플래너 대화">
            <div className="chat-messages" aria-live="polite" aria-busy={sending}>
              {messages.map((message) => (
                <article className={`chat-message ${message.role}`} key={message.id}>
                  <span className="chat-speaker">
                    {message.role === "assistant" ? "MAIRRY" : "나"}
                  </span>
                  <div className="chat-bubble">
                    <p>{message.text}</p>
                    {message.response && <ResponseEvidence response={message.response} />}
                  </div>
                </article>
              ))}
              {sending && (
                <article className="chat-message assistant chat-thinking" role="status">
                  <span className="chat-speaker">MAIRRY</span>
                  <div className="chat-bubble">
                    <span className="chat-thinking-dots" aria-hidden="true">
                      <i />
                      <i />
                      <i />
                    </span>
                    <span className="sr-only">계약과 자금 정보를 확인하고 있습니다.</span>
                  </div>
                </article>
              )}
              <div ref={conversationEnd} />
            </div>

            {error && (
              <div className="chat-error" role="alert">
                <span>{error}</span>
                {failedQuestion && (
                  <button
                    type="button"
                    disabled={sending}
                    onClick={() => void ask(failedQuestion, false)}
                  >
                    다시 시도
                  </button>
                )}
              </div>
            )}

            <form className="chat-composer" onSubmit={submit}>
              <label className="sr-only" htmlFor="chat-message">
                AI 플래너에게 질문하기
              </label>
              <textarea
                id="chat-message"
                value={input}
                maxLength={2000}
                rows={2}
                disabled={sending}
                placeholder="예: 웨딩홀 잔금일과 남은 금액을 알려줘"
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.nativeEvent.isComposing) return;
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
              />
              <div>
                <span>{input.length}/2000</span>
                <button type="submit" disabled={sending || !input.trim()}>
                  {sending ? "확인 중" : "질문 보내기"}
                </button>
              </div>
            </form>
          </section>

          <aside className="chat-guide" aria-labelledby="suggestions-title">
            <span className="chat-eyebrow">QUICK QUESTIONS</span>
            <h2 id="suggestions-title">이렇게 물어보세요</h2>
            <div className="chat-suggestions">
              {SUGGESTED_QUESTIONS.map((question) => (
                <button
                  type="button"
                  key={question}
                  disabled={sending}
                  onClick={() => void ask(question)}
                >
                  <span>{question}</span>
                  <b aria-hidden="true">→</b>
                </button>
              ))}
            </div>
            <div className="chat-scope-note">
              <strong>답변 범위</strong>
              <p>
                계약 일정·금액·취소 조건, 자금 현황과 추가 지출 시뮬레이션을 질문할 수 있습니다.
              </p>
              <small>근거가 없거나 지원하지 않는 질문에는 답을 만들어내지 않습니다.</small>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}

function ResponseEvidence({ response }: { response: ChatResponse }) {
  return (
    <div className="chat-evidence">
      {response.answerType === "NOT_FOUND" && (
        <p className="chat-no-result">확인 가능한 계약 또는 계산 근거가 없습니다.</p>
      )}
      {response.citations.length > 0 && (
        <section aria-label="계약 근거">
          <h3>계약 근거</h3>
          <div className="chat-citations">
            {response.citations.map((citation, index) => (
              <Link
                className="chat-citation"
                href={`/contracts/${citation.contractId}`}
                key={`${citation.contractId}-${index}`}
              >
                <strong>{citation.label}</strong>
                <blockquote>{citation.sourceText}</blockquote>
                <span>계약 상세 보기 →</span>
              </Link>
            ))}
          </div>
        </section>
      )}
      {response.calculation && <CalculationEvidence calculation={response.calculation} />}
    </div>
  );
}

function CalculationEvidence({
  calculation,
}: {
  calculation: FinanceCalculation | SimulationCalculation;
}) {
  const isFinance = "availableAsset" in calculation;
  const rows = isFinance
    ? [
        ["가용 자산", calculation.availableAsset],
        ["남은 지출", calculation.remainingExpense],
        ["예상 잔액", calculation.expectedBalance],
      ]
    : [
        ["현재 예상 잔액", calculation.currentExpectedBalance],
        ["추가 지출 반영 후", calculation.simulatedExpectedBalance],
        ["부족 금액", calculation.shortageAmount],
      ];

  return (
    <section className="chat-calculation" aria-label="계산 근거">
      <div>
        <h3>서버 계산 결과</h3>
        <time dateTime={calculation.calculatedAt}>
          {formatCalculatedAt(calculation.calculatedAt)} 기준
        </time>
      </div>
      <dl>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{formatWon(value as number)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
