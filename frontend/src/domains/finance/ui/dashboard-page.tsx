"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useDemoSession } from "@/domains/auth";
import { getWeddingPlan, saveWeddingPlan } from "@/domains/wedding-plan/api/wedding-plan-api";
import type { WeddingPlan } from "@/domains/wedding-plan/model/types";
import { ApiError } from "@/shared/api/api-client";
import { getFinanceSummary } from "../api/finance-api";
import { parseCalendarDate } from "../model/date";
import type { FinanceSummary } from "../model/types";
import { FinanceDashboard } from "./finance-dashboard";

const MAX_SAFE_WON = Number.MAX_SAFE_INTEGER;

function messageFrom(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function parseWonInput(value: string): number | null {
  if (!/^\d+$/.test(value)) return null;
  const amount = Number(value);
  return Number.isSafeInteger(amount) && amount >= 0 && amount <= MAX_SAFE_WON ? amount : null;
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

  if (isLoadingPlan || (isLoadingFinance && summary === null)) return <DashboardSkeleton />;
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
  if (financeError && summary === null)
    return <PageError message={financeError} onRetry={() => void loadFinance()} />;
  if (summary === null) return null;
  return (
    <FinanceDashboard
      plan={plan}
      summary={summary}
      financeError={financeError}
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
    if (!parseCalendarDate(weddingDate)) return setError("결혼 예정일을 선택해 주세요.");
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

  return (
    <main style={{ maxWidth: 1200, margin: "0 auto", padding: 32 }}>
      <header
        style={{
          marginBottom: 28,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 16,
        }}
      >
        <div>
          <p style={{ color: "var(--primary)", fontWeight: 700 }}>MAIRRY</p>
          <h1>우리 결혼 자금 현황</h1>
          {session !== null && (
            <p className="dashboard-user" aria-label="현재 데모 사용자">
              {session.user.displayName}님, 반가워요.
            </p>
          )}
          <p style={{ color: "var(--muted)" }}>
            계약서를 등록하면 남은 지급 일정과 예상 잔액을 계산합니다.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Link href="/contracts" className="secondary-link">
            계약 관리
          </Link>
          <Link href="/documents/upload" className="primary-link">
            계약서 업로드
          </Link>
        </div>
      </header>
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 16,
        }}
      >
        <SummaryCard label="현재 가용자금" value={formatWon(preview.availableAsset)} />
        <SummaryCard label="남은 확정지출" value={formatWon(preview.remainingExpense)} />
        <SummaryCard label="예상 잔액" value={formatWon(preview.expectedBalance)} emphasized />
        <SummaryCard label="가장 가까운 결제" value={preview.nearestPayment} />
      </section>
    </main>
  );
}

function DashboardSkeleton() {
  return (
    <main className="finance-loading" aria-busy="true" aria-live="polite">
      <div className="skeleton summary-skeleton" />
      <div className="finance-loading-grid">
        <div className="skeleton" />
        <div className="skeleton" />
      </div>
      <p>금융 현황을 불러오고 있어요...</p>
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
