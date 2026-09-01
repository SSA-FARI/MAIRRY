"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useDemoSession } from "@/domains/auth";
import { ApiError } from "@/shared/api/api-client";
import { formatWon } from "@/shared/lib/money";
import { getWeddingPlan, saveWeddingPlan } from "@/domains/wedding-plan/api/wedding-plan-api";
import type { WeddingPlan } from "@/domains/wedding-plan/model/types";
import { getFinanceSummary, simulateAdditionalExpense } from "../api/finance-api";
import type { FinanceSummary, SimulationResult, UpcomingPayment } from "../model/types";
import {
  formatDayStatus,
  formatShortDate,
  formatWeddingDate,
  isInCurrentMonth,
  monthKey,
  parseCalendarDate,
} from "../model/date";

const MAX_SAFE_WON = Number.MAX_SAFE_INTEGER;
type TimelineFilter = "all" | "upcoming" | "paid";

function messageFrom(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function parseWonInput(value: string): number | null {
  if (!/^\d+$/.test(value)) return null;
  const amount = Number(value);
  return Number.isSafeInteger(amount) && amount >= 0 && amount <= MAX_SAFE_WON ? amount : null;
}

function clampProgress(value: number, total: number): number {
  if (!Number.isFinite(value) || !Number.isFinite(total) || total <= 0) return 0;
  return Math.min(100, Math.max(0, (Math.max(0, value) / total) * 100));
}

export function DashboardPage() {
  const { session } = useDemoSession();
  const [plan, setPlan] = useState<WeddingPlan | null>(null);
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [isLoadingPlan, setIsLoadingPlan] = useState(true);
  const [isLoadingFinance, setIsLoadingFinance] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [financeError, setFinanceError] = useState<string | null>(null);

  const loadFinance = useCallback(async (signal?: AbortSignal) => {
    setIsLoadingFinance(true);
    setFinanceError(null);
    try {
      setSummary(await getFinanceSummary(signal));
    } catch (error) {
      if (!signal?.aborted) setFinanceError(messageFrom(error, "금융 현황을 불러오지 못했습니다."));
    } finally {
      if (!signal?.aborted) setIsLoadingFinance(false);
    }
  }, []);

  const loadPlan = useCallback(
    async (signal?: AbortSignal) => {
      setIsLoadingPlan(true);
      setPlanError(null);
      try {
        const loadedPlan = await getWeddingPlan(signal);
        setPlan(loadedPlan);
        await loadFinance(signal);
      } catch (error) {
        if (signal?.aborted) return;
        if (error instanceof ApiError && error.status === 404) {
          setPlan(null);
          setSummary(null);
        } else setPlanError(messageFrom(error, "결혼 준비 정보를 불러오지 못했습니다."));
      } finally {
        if (!signal?.aborted) setIsLoadingPlan(false);
      }
    },
    [loadFinance],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadPlan(controller.signal);
    return () => controller.abort();
  }, [loadPlan]);

  if (isLoadingPlan) return <DashboardSkeleton />;
  if (planError) return <PageError message={planError} onRetry={() => void loadPlan()} />;
  if (plan === null)
    return (
      <WeddingPlanSetup
        onSaved={(saved) => {
          setPlan(saved);
          void loadFinance();
        }}
      />
    );
  return (
    <FinanceDashboard
      plan={plan}
      summary={summary}
      financeError={financeError}
      isLoading={isLoadingFinance}
      displayName={session?.user.displayName ?? "데모 사용자"}
      onRetry={() => void loadFinance()}
    />
  );
}

function WeddingPlanSetup({ onSaved }: { onSaved: (plan: WeddingPlan) => void }) {
  const [weddingDate, setWeddingDate] = useState("");
  const [assetInput, setAssetInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amount = parseWonInput(assetInput);
    const date = parseCalendarDate(weddingDate);
    if (!date) return setError("결혼 예정일을 선택해 주세요.");
    if (amount === null) return setError("공동 자산은 0원 이상의 안전한 정수로 입력해 주세요.");
    setError(null);
    setIsSaving(true);
    try {
      onSaved(await saveWeddingPlan({ weddingDate, availableAsset: amount }));
    } catch (saveError) {
      setError(messageFrom(saveError, "초기 설정을 저장하지 못했습니다."));
      setIsSaving(false);
    }
  }
  return (
    <main className="setup-page">
      <form className="setup-card" onSubmit={submit} aria-busy={isSaving}>
        <p className="brand">MAIRRY</p>
        <p className="eyebrow">WEDDING FINANCE PLANNER</p>
        <h1>결혼 준비를 시작해볼까요?</h1>
        <p className="setup-copy">
          두 가지 정보만 입력하면 확정된 계약을 기준으로 자금 계획을 보여드려요.
        </p>
        <label htmlFor="wedding-date">결혼 예정일</label>
        <input
          id="wedding-date"
          type="date"
          value={weddingDate}
          onChange={(event) => setWeddingDate(event.target.value)}
          required
        />
        <label htmlFor="available-asset">현재 준비된 공동 현금 자산</label>
        <div className="money-input">
          <input
            id="available-asset"
            inputMode="numeric"
            value={assetInput ? Number(assetInput).toLocaleString("ko-KR") : ""}
            onChange={(event) => setAssetInput(event.target.value.replace(/\D/g, ""))}
            placeholder="30,000,000"
            required
          />
          <span>원</span>
        </div>
        <p className="field-help">
          초기 설정의 대표 공동 현금 자산이며, 향후 등록한 전체 자산 합계와는 다를 수 있어요.
        </p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button className="primary-button" disabled={isSaving}>
          {isSaving ? "저장하고 있어요..." : "계획 시작하기"}
        </button>
      </form>
    </main>
  );
}

function FinanceDashboard({
  plan,
  summary,
  financeError,
  isLoading,
  displayName,
  onRetry,
}: {
  plan: WeddingPlan;
  summary: FinanceSummary | null;
  financeError: string | null;
  isLoading: boolean;
  displayName: string;
  onRetry: () => void;
}) {
  const [filter, setFilter] = useState<TimelineFilter>("all");
  if (isLoading && summary === null) return <DashboardSkeleton />;
  if (financeError && summary === null)
    return <PageError message={financeError} onRetry={onRetry} />;
  if (summary === null) return null;
  const shortageAmount = Math.max(0, -summary.expectedBalance);
  const weddingDay = formatDayStatus(plan.weddingDate);
  return (
    <div className="dashboard-shell">
      <div className="demo-banner">데모 계정으로 서비스를 체험하고 있어요.</div>
      <header className="dashboard-header">
        <span className="brand">MAIRRY</span>
        <nav aria-label="대시보드 영역">
          <a href="#dashboard">대시보드</a>
          <a href="#timeline">지급 일정</a>
          <a href="#simulator">시뮬레이션</a>
        </nav>
        <Link className="upload-link" href="/documents/upload">
          계약서 업로드
        </Link>
      </header>
      <main id="dashboard" className="dashboard-main">
        <p className="welcome">{displayName}님, 결혼 자금 현황을 확인해 보세요.</p>
        {financeError && <InlineError message={financeError} onRetry={onRetry} />}
        <section className="summary-grid" aria-label="금융 요약">
          <article className="hero-card">
            <div className="date-pill">
              ▣ {formatWeddingDate(plan.weddingDate)} · {weddingDay.label}
            </div>
            <h1>
              지금까지 모은 자금과
              <br />
              남은 지출을 한눈에 확인해요
            </h1>
            <div className="amount-grid">
              <Amount label="총 자산" value={summary.availableAsset} />
              <Amount label="남은 지출" value={summary.remainingExpense} />
              <Amount
                label="예상 잔액"
                value={summary.expectedBalance}
                danger={summary.expectedBalance < 0}
              />
            </div>
            {shortageAmount > 0 ? (
              <p className="shortage">
                ⚠ 현재 계획대로 진행하면 {formatWon(shortageAmount)}이 부족해요.
              </p>
            ) : (
              <p className="healthy">✓ 남은 지출을 반영해도 예산 안에서 준비되고 있어요.</p>
            )}
          </article>
          <div className="side-stack">
            <NextPaymentCard payment={summary.nearestPayment} />
            <a className="mini-card" href="#timeline">
              <span>이번 달 예정 지출</span>
              <strong>{formatWon(monthlyTotal(summary.timeline))}</strong>
              <small>전체 일정 보기 →</small>
            </a>
          </div>
        </section>
        <TimelineSection
          payments={summary.timeline}
          filter={filter}
          onFilter={setFilter}
          shortageAmount={shortageAmount}
        />
        <Simulator totalAsset={summary.availableAsset} expectedBalance={summary.expectedBalance} />
      </main>
      <footer>MAIRRY · 데모 계정으로 제공되는 서비스입니다.</footer>
    </div>
  );
}

function Amount({
  label,
  value,
  danger = false,
}: {
  label: string;
  value: number;
  danger?: boolean;
}) {
  return (
    <div>
      <span>{label}</span>
      <strong className={danger ? "danger" : ""}>{formatWon(value)}</strong>
    </div>
  );
}
function NextPaymentCard({ payment }: { payment: UpcomingPayment | null }) {
  if (!payment)
    return (
      <article className="next-card">
        <span>다음 지급</span>
        <p className="empty-copy">예정된 지급 일정이 없습니다.</p>
      </article>
    );
  const day = formatDayStatus(payment.dueDate);
  return (
    <article className="next-card">
      <span>다음 지급</span>
      <h2>
        ◈ {payment.company} · {payment.name}
      </h2>
      <strong>{formatWon(payment.amount)}</strong>
      <div>
        <time>{formatShortDate(payment.dueDate)}</time>
        <em className={day.overdue ? "overdue" : ""}>
          {day.overdue ? `연체 ${day.label}` : day.label}
        </em>
      </div>
    </article>
  );
}

function TimelineSection({
  payments,
  filter,
  onFilter,
  shortageAmount,
}: {
  payments: UpcomingPayment[];
  filter: TimelineFilter;
  onFilter: (value: TimelineFilter) => void;
  shortageAmount: number;
}) {
  const groups = useMemo(() => {
    const map = new Map<string, UpcomingPayment[]>();
    const visible = filter === "paid" ? [] : payments;
    for (const payment of visible)
      map.set(monthKey(payment.dueDate), [...(map.get(monthKey(payment.dueDate)) ?? []), payment]);
    return [...map.entries()];
  }, [filter, payments]);
  const currentMonth = payments.filter((payment) => isInCurrentMonth(payment.dueDate));
  return (
    <section id="timeline" className="section-block">
      <div className="section-heading">
        <h2>지급 일정</h2>
        <div className="filters">
          {(
            [
              ["all", "전체보기"],
              ["upcoming", "지급 예정"],
              ["paid", "지급 완료"],
            ] as const
          ).map(([key, label]) => (
            <button key={key} aria-pressed={filter === key} onClick={() => onFilter(key)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="timeline-layout">
        <div>
          {groups.length === 0 ? (
            <EmptyTimeline paid={filter === "paid"} />
          ) : (
            groups.map(([month, items]) => (
              <div className="month-group" key={month}>
                <h3>{month}</h3>
                <div className="timeline-list">
                  {items.map((payment, index) => (
                    <PaymentRow
                      key={`${payment.contractId}-${payment.dueDate}-${payment.name}-${index}`}
                      payment={payment}
                    />
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
        <aside>
          <article className="detail-card">
            <h3>이번 달 지출 세부내역</h3>
            {currentMonth.length === 0 ? (
              <p className="empty-copy">이번 달 예정된 지출이 없습니다.</p>
            ) : (
              <ul>
                {currentMonth.map((payment, index) => (
                  <li key={`${payment.contractId}-${index}`}>
                    <span>{payment.company}</span>
                    <strong>{formatWon(payment.amount)}</strong>
                  </li>
                ))}
              </ul>
            )}
            <div className="detail-total">
              <span>합계</span>
              <strong>{formatWon(monthlyTotal(payments))}</strong>
            </div>
          </article>
          <article className={shortageAmount > 0 ? "budget-card danger-card" : "budget-card"}>
            <h3>{shortageAmount > 0 ? "예산 부족 안내" : "예산 상태"}</h3>
            <p>
              {shortageAmount > 0
                ? `현재 계획대로면 ${formatWon(shortageAmount)}이 부족할 것으로 예상돼요.`
                : "남은 지출을 반영해도 예산 안에서 준비되고 있어요."}
            </p>
          </article>
        </aside>
      </div>
    </section>
  );
}

function PaymentRow({ payment }: { payment: UpcomingPayment }) {
  const day = formatDayStatus(payment.dueDate);
  return (
    <article className="payment-row">
      <span className={day.overdue ? "timeline-dot overdue-dot" : "timeline-dot"} />
      <span className="category-icon" aria-hidden="true">
        ◈
      </span>
      <div className="payment-copy">
        <strong>{payment.company}</strong>
        <span>
          {payment.name} · {formatShortDate(payment.dueDate)}
        </span>
      </div>
      <div className="payment-amount">
        <strong>{formatWon(payment.amount)}</strong>
        <span className={day.overdue ? "danger" : ""}>
          {day.overdue ? `연체 ${day.label}` : `${day.label} · 지급 예정`}
        </span>
      </div>
    </article>
  );
}
function EmptyTimeline({ paid }: { paid: boolean }) {
  return (
    <div className="empty-state">
      <strong>
        {paid ? "지급 완료 항목을 제공하는 API가 아직 없어요." : "아직 확정된 계약이 없어요."}
      </strong>
      <p>
        {paid
          ? "현재 지급 타임라인 API는 확정된 미지급 일정만 제공합니다."
          : "계약서를 등록하고 검수하면 지급 일정이 여기에 표시돼요."}
      </p>
      {!paid && <Link href="/documents/upload">계약서 등록하기</Link>}
    </div>
  );
}

function Simulator({
  totalAsset,
  expectedBalance,
}: {
  totalAsset: number;
  expectedBalance: number;
}) {
  const [name, setName] = useState("");
  const [amountInput, setAmountInput] = useState("");
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amount = parseWonInput(amountInput);
    if (!name.trim()) return setError("추가 지출 항목명을 입력해 주세요.");
    if (amount === null || amount === 0)
      return setError("추가 지출은 1원 이상의 안전한 정수로 입력해 주세요.");
    setError(null);
    setIsSubmitting(true);
    try {
      setResult(await simulateAdditionalExpense({ name: name.trim(), amount }));
    } catch (simulationError) {
      setError(messageFrom(simulationError, "시뮬레이션에 실패했습니다. 다시 시도해 주세요."));
    } finally {
      setIsSubmitting(false);
    }
  }
  const shownBalance = result?.simulatedExpectedBalance ?? expectedBalance;
  return (
    <section id="simulator" className="section-block">
      <h2>추가 지출 시뮬레이션</h2>
      <p className="section-copy">
        갑자기 생긴 지출을 더하면 예상 잔액이 어떻게 바뀌는지 서버 계산으로 확인해요.
      </p>
      <div className="simulator-card">
        <form onSubmit={submit} aria-busy={isSubmitting}>
          <span>현재 예상 잔액</span>
          <strong className={expectedBalance < 0 ? "danger large-money" : "large-money"}>
            {formatWon(expectedBalance)}
          </strong>
          <label htmlFor="expense-name">추가 지출 항목</label>
          <input
            id="expense-name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              setResult(null);
            }}
            placeholder="예: 가전 비용"
          />
          <label htmlFor="expense-amount">추가로 예상되는 지출</label>
          <div className="money-input">
            <input
              id="expense-amount"
              inputMode="numeric"
              value={amountInput ? Number(amountInput).toLocaleString("ko-KR") : ""}
              onChange={(event) => {
                setAmountInput(event.target.value.replace(/\D/g, ""));
                setResult(null);
              }}
              placeholder="5,000,000"
            />
            <span>원</span>
          </div>
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          <button className="primary-button compact" disabled={isSubmitting}>
            {isSubmitting ? "계산 중..." : "▣ 계산하기"}
          </button>
        </form>
        <div className="result-panel" aria-live="polite">
          <span>{result ? "추가 지출 후 예상 잔액" : "계산 결과가 여기에 표시돼요"}</span>
          <strong className={shownBalance < 0 ? "danger large-money" : "large-money"}>
            {formatWon(shownBalance)}
          </strong>
          <Progress
            label="현재"
            value={result?.currentExpectedBalance ?? expectedBalance}
            total={totalAsset}
          />
          <Progress
            label="추가 지출 이후"
            value={result?.simulatedExpectedBalance ?? expectedBalance}
            total={totalAsset}
            muted={!result}
          />
          {result && result.shortageAmount > 0 && (
            <p className="shortage">⚠ {formatWon(result.shortageAmount)}이 부족해질 수 있어요.</p>
          )}
        </div>
      </div>
    </section>
  );
}

function Progress({
  label,
  value,
  total,
  muted = false,
}: {
  label: string;
  value: number;
  total: number;
  muted?: boolean;
}) {
  return (
    <div className={muted ? "progress muted" : "progress"}>
      <div>
        <span>{label}</span>
        <span>{formatWon(value)}</span>
      </div>
      <div className="progress-track">
        <span style={{ width: `${clampProgress(value, total)}%` }} />
      </div>
    </div>
  );
}
function monthlyTotal(payments: UpcomingPayment[]): number {
  return payments
    .filter((payment) => isInCurrentMonth(payment.dueDate))
    .reduce((total, payment) => total + payment.amount, 0);
}
function DashboardSkeleton() {
  return (
    <main className="dashboard-loading" aria-busy="true" aria-live="polite">
      <div className="skeleton wide" />
      <div className="skeleton-grid">
        <div className="skeleton" />
        <div className="skeleton" />
      </div>
      <p>자금 현황을 불러오고 있어요...</p>
    </main>
  );
}
function PageError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <main className="page-error">
      <div>
        <p role="alert">{message}</p>
        <button className="primary-button compact" onClick={onRetry}>
          다시 시도
        </button>
      </div>
    </main>
  );
}
function InlineError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="inline-error" role="alert">
      <span>{message}</span>
      <button onClick={onRetry}>다시 시도</button>
    </div>
  );
}
