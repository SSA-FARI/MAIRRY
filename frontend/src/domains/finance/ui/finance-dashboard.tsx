"use client";

import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";
import { formatWon } from "@/shared/lib/money";
import type { WeddingPlan } from "@/domains/wedding-plan/model/types";
import { simulateAdditionalExpense } from "../api/finance-api";
import {
  buildCalendarCells,
  calendarMonthFrom,
  currentCalendarMonth,
  formatIsoDate,
  shiftCalendarMonth,
} from "../model/calendar";
import { formatDayStatus, formatShortDate, formatWeddingDate } from "../model/date";
import type { FinanceSummary, SimulationResult, UpcomingPayment } from "../model/types";

type TimelineFilter = "all" | "upcoming" | "paid";
const MAX_SAFE_WON = Number.MAX_SAFE_INTEGER;

function safeRatio(value: number, total: number): number {
  if (!Number.isFinite(value) || !Number.isFinite(total) || total <= 0) return 0;
  return Math.min(100, Math.max(0, (Math.max(0, value) / total) * 100));
}

function compactWon(value: number): string {
  if (value >= 10_000)
    return `${new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 }).format(value / 10_000)}만`;
  return new Intl.NumberFormat("ko-KR").format(value);
}

function todayIso(now = new Date()): string {
  return formatIsoDate({ year: now.getFullYear(), month: now.getMonth() + 1, day: now.getDate() });
}

export function FinanceDashboard({
  plan,
  summary,
  financeError,
  displayName,
  onRetry,
}: {
  plan: WeddingPlan;
  summary: FinanceSummary;
  financeError: string | null;
  displayName: string;
  onRetry: () => void;
}) {
  const today = todayIso();
  const oldestOverdue = [...summary.timeline]
    .filter((payment) => payment.dueDate < today)
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate))[0];
  const initialDate = oldestOverdue?.dueDate ?? summary.nearestPayment?.dueDate ?? today;
  const [filter, setFilter] = useState<TimelineFilter>("all");
  const [visibleMonth, setVisibleMonth] = useState(
    calendarMonthFrom(initialDate) ?? currentCalendarMonth(),
  );
  const [selectedDate, setSelectedDate] = useState(initialDate);
  const [simulatorOpen, setSimulatorOpen] = useState(false);
  const shortage = Math.max(0, -summary.expectedBalance);
  function selectPaymentDate(date: string) {
    const month = calendarMonthFrom(date);
    if (month) setVisibleMonth(month);
    setSelectedDate(date);
  }

  return (
    <div className="finance-shell">
      <header className="finance-header">
        <Link className="finance-logo" href="/">
          MAIRRY
        </Link>
        <nav aria-label="주요 메뉴">
          <a className="active" href="#dashboard">
            금융 대시보드
          </a>
          <Link href="/documents/upload">계약서</Link>
          <span aria-disabled="true">AI 질문</span>
        </nav>
        <div className="finance-header-actions">
          <span className="demo-badge">DEMO · {displayName}</span>
        </div>
      </header>

      <main id="dashboard" className="finance-main">
        {financeError && <InlineError message={financeError} onRetry={onRetry} />}
        <FinanceSummaryRow
          plan={plan}
          summary={summary}
          shortage={shortage}
          onSimulate={() => setSimulatorOpen(true)}
        />
        <section className="finance-analysis-grid" aria-label="자금 분석">
          <AssetAllocationChart summary={summary} />
          <MonthlyPaymentChart
            payments={summary.timeline}
            nearestPayment={oldestOverdue ?? summary.nearestPayment}
            onPaymentSelect={(payment) => selectPaymentDate(payment.dueDate)}
          />
          <SelectedDatePayments
            payments={filter === "paid" ? [] : summary.timeline}
            selectedDate={selectedDate}
            paidFilterSelected={filter === "paid"}
          />
        </section>
        <section className="finance-calendar-section" aria-label="월간 지급 일정">
          <PaymentCalendar
            payments={summary.timeline}
            filter={filter}
            onFilter={setFilter}
            visibleMonth={visibleMonth}
            onMonthChange={setVisibleMonth}
            selectedDate={selectedDate}
            onDateSelect={selectPaymentDate}
          />
        </section>
      </main>
      <footer className="finance-footer">MAIRRY · 계약 기반 결혼 자금 플래너</footer>
      {simulatorOpen && (
        <ExpenseSimulatorDialog
          totalAsset={summary.availableAsset}
          expectedBalance={summary.expectedBalance}
          onClose={() => setSimulatorOpen(false)}
        />
      )}
    </div>
  );
}

function FinanceSummaryRow({
  plan,
  summary,
  shortage,
  onSimulate,
}: {
  plan: WeddingPlan;
  summary: FinanceSummary;
  shortage: number;
  onSimulate: () => void;
}) {
  const weddingDay = formatDayStatus(plan.weddingDate);
  const expenseRatio = safeRatio(summary.remainingExpense, summary.availableAsset);
  return (
    <section className="finance-summary-row" aria-label="금융 요약">
      <article className="summary-date-card">
        <span>결혼식</span>
        <strong>{weddingDay.label}</strong>
        <small>{formatWeddingDate(plan.weddingDate)}</small>
      </article>
      <SummaryMetric label="총 자산" value={summary.availableAsset} note="확인된 전체 자산" />
      <SummaryMetric
        label="남은 지출"
        value={summary.remainingExpense}
        note={`총자산의 ${Math.round(expenseRatio)}%`}
      />
      <SummaryMetric
        label="예상 잔액"
        value={summary.expectedBalance}
        note={shortage > 0 ? `부족 ${formatWon(shortage)}` : "지출 반영 후 잔액"}
        danger={shortage > 0}
        emphasized
      />
      <article className={shortage > 0 ? "summary-status danger-status" : "summary-status"}>
        <span>예산 상태</span>
        <strong>{shortage > 0 ? "⚠ 예산 조정 필요" : "✓ 안정적으로 준비 중"}</strong>
        <small>
          {shortage > 0
            ? `${formatWon(shortage)} 부족 예상`
            : `잔액 ${compactWon(summary.expectedBalance)}원 예상`}
        </small>
        <button className="summary-simulate-button" onClick={onSimulate}>
          추가 지출 계산
        </button>
      </article>
    </section>
  );
}

function SummaryMetric({
  label,
  value,
  note,
  danger = false,
  emphasized = false,
}: {
  label: string;
  value: number;
  note: string;
  danger?: boolean;
  emphasized?: boolean;
}) {
  return (
    <article
      className={`summary-metric${emphasized ? " emphasized" : ""}${danger ? " danger-metric" : ""}`}
    >
      <span>{label}</span>
      <strong>{formatWon(value)}</strong>
      <small>{note}</small>
    </article>
  );
}

function AssetAllocationChart({ summary }: { summary: FinanceSummary }) {
  const expensePercent = safeRatio(summary.remainingExpense, summary.availableAsset);
  const balancePercent = safeRatio(summary.expectedBalance, summary.availableAsset);
  const circumference = 289;
  return (
    <article className="finance-panel allocation-panel">
      <div className="panel-heading">
        <div>
          <span className="panel-eyebrow">ASSET ALLOCATION</span>
          <h2>자금 현황</h2>
        </div>
        <span className="data-badge">실시간 계산</span>
      </div>
      <div className="allocation-content">
        <figure
          className="donut-figure"
          aria-label={`남은 지출 ${formatWon(summary.remainingExpense)}, 예상 잔액 ${formatWon(summary.expectedBalance)}`}
        >
          <svg viewBox="0 0 112 112" role="img" aria-hidden="true">
            <circle className="donut-base" cx="56" cy="56" r="46" />
            <circle
              className="donut-expense"
              cx="56"
              cy="56"
              r="46"
              style={{
                strokeDasharray: `${(expensePercent / 100) * circumference} ${circumference}`,
              }}
            />
            {summary.expectedBalance > 0 && (
              <circle
                className="donut-balance"
                cx="56"
                cy="56"
                r="46"
                style={{
                  strokeDasharray: `${(balancePercent / 100) * circumference} ${circumference}`,
                  strokeDashoffset: -((expensePercent / 100) * circumference),
                }}
              />
            )}
          </svg>
          <figcaption>
            <span>사용 가능 잔액</span>
            <strong>{formatWon(summary.expectedBalance)}</strong>
          </figcaption>
        </figure>
        <dl className="chart-legend">
          <div>
            <dt>
              <i className="legend-navy" />
              남은 지출
            </dt>
            <dd>{formatWon(summary.remainingExpense)}</dd>
          </div>
          <div>
            <dt>
              <i className={summary.expectedBalance < 0 ? "legend-danger" : "legend-purple"} />
              예상 잔액
            </dt>
            <dd>{formatWon(summary.expectedBalance)}</dd>
          </div>
          <div>
            <dt>총 자산 대비 지출</dt>
            <dd>{Math.round(expensePercent)}%</dd>
          </div>
        </dl>
      </div>
    </article>
  );
}

function MonthlyPaymentChart({
  payments,
  nearestPayment,
  onPaymentSelect,
}: {
  payments: UpcomingPayment[];
  nearestPayment: UpcomingPayment | null;
  onPaymentSelect: (payment: UpcomingPayment) => void;
}) {
  const months = useMemo(() => {
    const grouped = new Map<string, { label: string; amount: number }>();
    for (const payment of payments) {
      const key = payment.dueDate.slice(0, 7);
      const parsedMonth = Number(key.slice(5, 7));
      const current = grouped.get(key) ?? { label: `${parsedMonth}월`, amount: 0 };
      grouped.set(key, { ...current, amount: current.amount + payment.amount });
    }
    return [...grouped.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(0, 6)
      .map(([, value]) => value);
  }, [payments]);
  const max = Math.max(0, ...months.map((month) => month.amount));
  return (
    <article className="finance-panel monthly-panel">
      <div className="panel-heading">
        <div>
          <span className="panel-eyebrow">UPCOMING CASH FLOW</span>
          <h2>월별 지급 예정</h2>
        </div>
        <span>{months.length}개월</span>
      </div>
      {months.length === 0 ? (
        <EmptyPayments />
      ) : (
        <div className="monthly-bars" role="list" aria-label="월별 지급 예정 금액">
          {months.map((month) => (
            <div
              className="monthly-bar-row"
              role="listitem"
              key={month.label}
              tabIndex={0}
              title={`${month.label} ${formatWon(month.amount)}`}
            >
              <span>{month.label}</span>
              <div>
                <i style={{ width: `${safeRatio(month.amount, max)}%` }} />
              </div>
              <strong>{formatWon(month.amount)}</strong>
            </div>
          ))}
        </div>
      )}
      <NextPaymentCompact payment={nearestPayment} onSelect={onPaymentSelect} />
    </article>
  );
}

function SelectedDatePayments({
  payments,
  selectedDate,
  paidFilterSelected,
}: {
  payments: UpcomingPayment[];
  selectedDate: string;
  paidFilterSelected: boolean;
}) {
  const selected = payments.filter((payment) => payment.dueDate === selectedDate);
  return (
    <article className="finance-panel selected-date-panel">
      <div className="panel-heading">
        <div>
          <span className="panel-eyebrow">SELECTED PAYMENTS</span>
          <h2>선택한 날짜의 지급 내역</h2>
        </div>
        <strong>{selectedDate.replaceAll("-", ".")}</strong>
      </div>
      <div className="selected-payment-list">
        {paidFilterSelected ? (
          <p className="contract-note">현재 API는 완료 지급 내역을 제공하지 않습니다.</p>
        ) : selected.length === 0 ? (
          <p>
            선택한 날짜에는 지급 일정이 없습니다.
            <br />
            Calendar에서 지급일이 표시된 날짜를 선택해보세요.
          </p>
        ) : (
          selected.map((payment, index) => (
            <PaymentDetail payment={payment} key={`${payment.contractId}-${index}`} />
          ))
        )}
      </div>
      <details className="accessible-payment-list">
        <summary>전체 지급 일정 목록</summary>
        {payments.length === 0 ? (
          <EmptyPayments />
        ) : (
          payments.map((payment, index) => (
            <PaymentDetail payment={payment} key={`${payment.contractId}-all-${index}`} />
          ))
        )}
      </details>
    </article>
  );
}

function PaymentCalendar({
  payments,
  filter,
  onFilter,
  visibleMonth,
  onMonthChange,
  selectedDate,
  onDateSelect,
}: {
  payments: UpcomingPayment[];
  filter: TimelineFilter;
  onFilter: (filter: TimelineFilter) => void;
  visibleMonth: { year: number; month: number; day: number };
  onMonthChange: (month: { year: number; month: number; day: number }) => void;
  selectedDate: string;
  onDateSelect: (date: string) => void;
}) {
  const visiblePayments = useMemo(() => (filter === "paid" ? [] : payments), [filter, payments]);
  const byDate = useMemo(() => {
    const map = new Map<string, UpcomingPayment[]>();
    for (const payment of visiblePayments)
      map.set(payment.dueDate, [...(map.get(payment.dueDate) ?? []), payment]);
    return map;
  }, [visiblePayments]);
  const cells = useMemo(() => buildCalendarCells(visibleMonth), [visibleMonth]);
  const today = todayIso();
  return (
    <article id="timeline" className="finance-panel calendar-panel">
      <div className="calendar-topline">
        <div>
          <span className="panel-eyebrow">PAYMENT SCHEDULE</span>
          <h2>지급 일정 캘린더</h2>
        </div>
      </div>
      <div className="calendar-controls">
        <div className="calendar-filters">
          {(
            [
              ["all", "전체"],
              ["upcoming", "예정"],
              ["paid", "완료"],
            ] as const
          ).map(([key, label]) => (
            <button key={key} aria-pressed={filter === key} onClick={() => onFilter(key)}>
              {label}
            </button>
          ))}
        </div>
        <div className="calendar-navigation">
          <button
            aria-label="이전 달"
            onClick={() => onMonthChange(shiftCalendarMonth(visibleMonth, -1))}
          >
            ‹
          </button>
          <strong>
            {visibleMonth.year}년 {visibleMonth.month}월
          </strong>
          <button
            aria-label="다음 달"
            onClick={() => onMonthChange(shiftCalendarMonth(visibleMonth, 1))}
          >
            ›
          </button>
          <button
            className="today-button"
            onClick={() => {
              const month = currentCalendarMonth();
              onMonthChange(month);
              onDateSelect(today);
            }}
          >
            오늘
          </button>
        </div>
      </div>
      <div className="calendar-main">
        <div className="calendar-weekdays" aria-hidden="true">
          {["일", "월", "화", "수", "목", "금", "토"].map((day) => (
            <span key={day}>{day}</span>
          ))}
        </div>
        <div
          className="calendar-grid"
          role="grid"
          aria-label={`${visibleMonth.year}년 ${visibleMonth.month}월 지급 일정`}
        >
          {cells.map((cell, index) => {
            const items = byDate.get(cell.isoDate) ?? [];
            const overdue = items.some(() => formatDayStatus(cell.isoDate).overdue);
            const total = items.reduce((sum, item) => sum + item.amount, 0);
            return (
              <button
                key={cell.isoDate}
                role="gridcell"
                className={`${cell.inCurrentMonth ? "" : "outside-month"}${items.length ? " has-payment" : ""}${overdue ? " overdue-date" : ""}`}
                aria-label={`${cell.isoDate}, ${items.length ? `${overdue ? "연체" : "지급 예정"} ${items.length}건, ${formatWon(total)}` : "지급 일정 없음"}`}
                aria-selected={selectedDate === cell.isoDate}
                aria-current={cell.isoDate === today ? "date" : undefined}
                onClick={() => onDateSelect(cell.isoDate)}
                onKeyDown={(event) => {
                  const offset = {
                    ArrowLeft: -1,
                    ArrowRight: 1,
                    ArrowUp: -7,
                    ArrowDown: 7,
                  }[event.key];
                  if (offset === undefined) return;
                  const nextIndex = index + offset;
                  if (nextIndex < 0 || nextIndex >= cells.length) return;
                  event.preventDefault();
                  const buttons = event.currentTarget.parentElement?.querySelectorAll("button");
                  buttons?.item(nextIndex).focus();
                  onDateSelect(cells[nextIndex].isoDate);
                }}
              >
                <span>{cell.day}</span>
                {items.length > 0 && (
                  <>
                    <i>
                      {overdue ? "연체" : "예정"} · {items.length}건
                    </i>
                    <small className="calendar-payment-name">
                      {items
                        .slice(0, 2)
                        .map((item) => `${item.company} ${item.name}`)
                        .join(" · ")}
                      {items.length > 2 ? ` · +${items.length - 2}건` : ""}
                    </small>
                    <small className="calendar-payment-amount">{compactWon(total)}원</small>
                  </>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </article>
  );
}

function NextPaymentCompact({
  payment,
  onSelect,
}: {
  payment: UpcomingPayment | null;
  onSelect: (payment: UpcomingPayment) => void;
}) {
  if (!payment)
    return (
      <div className="next-payment-compact">
        <span>가장 가까운 지급</span>
        <p>예정된 지급이 없습니다.</p>
      </div>
    );
  const status = formatDayStatus(payment.dueDate);
  return (
    <button className="next-payment-compact" onClick={() => onSelect(payment)}>
      <span>가장 가까운 지급</span>
      <strong>
        {payment.company} · {payment.name}
      </strong>
      <b>{formatWon(payment.amount)}</b>
      <small>
        {formatShortDate(payment.dueDate)} ·{" "}
        {status.overdue ? `연체 ${status.label}` : status.label}
      </small>
    </button>
  );
}

function PaymentDetail({ payment }: { payment: UpcomingPayment }) {
  const status = formatDayStatus(payment.dueDate);
  return (
    <article className="payment-detail">
      <div>
        <strong>{payment.company}</strong>
        <span>
          {payment.name} · {formatWon(payment.amount)}
        </span>
      </div>
      <em className={status.overdue ? "overdue" : ""}>
        {status.overdue ? `연체 · ${status.label}` : `예정 · ${status.label}`}
      </em>
    </article>
  );
}

function EmptyPayments() {
  return (
    <p className="compact-empty">
      아직 확정된 지급 일정이 없어요.
      <br />
      계약서를 등록하고 검수하면 표시됩니다.
    </p>
  );
}

function ExpenseSimulatorDialog({
  totalAsset,
  expectedBalance,
  onClose,
}: {
  totalAsset: number;
  expectedBalance: number;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [amountInput, setAmountInput] = useState("");
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amount = Number(amountInput);
    if (!name.trim()) return setError("추가 지출 항목명을 입력해 주세요.");
    if (
      !/^\d+$/.test(amountInput) ||
      !Number.isSafeInteger(amount) ||
      amount <= 0 ||
      amount > MAX_SAFE_WON
    )
      return setError("추가 지출은 1원 이상의 안전한 정수로 입력해 주세요.");
    setError(null);
    setSubmitting(true);
    try {
      setResult(await simulateAdditionalExpense({ name: name.trim(), amount }));
    } catch {
      setError("시뮬레이션에 실패했습니다. 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  }
  const shown = result?.simulatedExpectedBalance ?? expectedBalance;
  return (
    <div
      className="simulator-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        id="simulator"
        className="simulator-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="simulator-title"
      >
        <header>
          <div>
            <span className="panel-eyebrow">WHAT-IF ANALYSIS</span>
            <h2 id="simulator-title">추가 지출 시뮬레이션</h2>
          </div>
          <button aria-label="시뮬레이터 닫기" onClick={onClose}>
            ×
          </button>
        </header>
        <div className="simulator-dialog-grid">
          <form onSubmit={submit} aria-busy={submitting}>
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
            <button className="navy-button" disabled={submitting}>
              {submitting ? "계산 중..." : "계산하기"}
            </button>
          </form>
          <div className="simulator-result" aria-live="polite">
            <span>{result ? "추가 지출 후 예상 잔액" : "현재 예상 잔액"}</span>
            <strong className={shown < 0 ? "danger" : ""}>{formatWon(shown)}</strong>
            <div className="simulator-comparison">
              <span>현재 {formatWon(result?.currentExpectedBalance ?? expectedBalance)}</span>
              <i>
                <b style={{ width: `${safeRatio(shown, totalAsset)}%` }} />
              </i>
            </div>
            {result?.shortageAmount ? (
              <p className="simulation-warning">⚠ 부족 {formatWon(result.shortageAmount)}</p>
            ) : (
              <p className="simulation-safe">✓ 원본 자금 계획은 변경되지 않습니다.</p>
            )}
          </div>
        </div>
      </section>
    </div>
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
