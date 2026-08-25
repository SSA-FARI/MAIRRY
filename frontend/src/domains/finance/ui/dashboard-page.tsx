import { formatWon } from "@/shared/lib/money";

const preview = {
  availableAsset: 30_000_000,
  remainingExpense: 20_000_000,
  expectedBalance: 10_000_000,
  nearestPayment: "2027.04.30 · A웨딩홀 잔금",
};

export function DashboardPage() {
  return (
    <main style={{ maxWidth: 1200, margin: "0 auto", padding: 32 }}>
      <header style={{ marginBottom: 28 }}>
        <p style={{ color: "var(--primary)", fontWeight: 700 }}>MAIRRY</p>
        <h1>우리 결혼 자금 현황</h1>
        <p style={{ color: "var(--muted)" }}>
          계약서를 등록하면 남은 지급 일정과 예상 잔액을 계산합니다.
        </p>
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

function SummaryCard({
  label,
  value,
  emphasized = false,
}: {
  label: string;
  value: string;
  emphasized?: boolean;
}) {
  return (
    <article
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 18,
        padding: 20,
        boxShadow: "0 8px 24px rgba(16, 24, 40, 0.05)",
      }}
    >
      <p style={{ color: "var(--muted)", marginTop: 0 }}>{label}</p>
      <strong
        data-testid={label === "예상 잔액" ? "expected-balance" : undefined}
        style={{ color: emphasized ? "var(--primary)" : "var(--text)", fontSize: 22 }}
      >
        {value}
      </strong>
    </article>
  );
}
