import path from "node:path";
import { expect, test } from "@playwright/test";

const demoContractPath = path.resolve(
  __dirname,
  "../../../backend/ai/document_extraction/fallback_assets/demo-wedding-hall-contract.pdf",
);

test("E2E-01 핵심 골든 패스", async ({ page }) => {
  test.setTimeout(120_000);

  await page.goto("/login");
  await page.getByRole("button", { name: "데모 계정으로 시작하기" }).click();

  await expect(page.getByRole("heading", { name: "결혼 준비를 시작해볼까요?" })).toBeVisible();
  await page.getByLabel("결혼 예정일").fill("2027-05-15");
  await page.getByLabel("현재 준비된 공동 현금 자산").fill("30000000");
  await page.getByRole("button", { name: "계획 시작하기" }).click();

  await expect(page.getByRole("heading", { name: "우리 결혼 자금 현황" })).toBeVisible();
  await expect(page.getByText("아직 확정된 지급 일정이 없어요.").first()).toBeVisible();

  await page.getByRole("link", { name: "계약서 업로드" }).click();
  await page.getByTestId("document-upload-input").setInputFiles(demoContractPath);

  await expect(page.getByRole("heading", { name: "계약 내용을 확인해 주세요" })).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByLabel("업체명 *")).toHaveValue("A웨딩홀");
  await expect(page.getByLabel("계약 총액 *")).toHaveValue("23000000");
  await expect(page.getByRole("group", { name: "지급항목 2" })).toContainText(
    "잔금 20,000,000원은 2027년 4월 30일까지",
  );
  await expect(page.getByRole("complementary", { name: "계약서 근거" })).toContainText(
    "예식일 90일 전까지 취소 시 계약금 전액 환급",
  );

  const balancePayment = page.getByRole("group", { name: "지급항목 2" });
  const balanceDate = balancePayment.getByLabel("지급일");
  await balanceDate.clear();
  await balanceDate.fill("2027-04-30");
  await page.getByRole("button", { name: "계약 확정" }).click();

  await expect(page).toHaveURL(/\/contracts\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "A웨딩홀" })).toBeVisible();

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "우리 결혼 자금 현황" })).toBeVisible();
  const financeSummary = page.getByRole("region", { name: "금융 요약" });
  await expect(financeSummary).toContainText("20,000,000원");
  await expect(financeSummary).toContainText("10,000,000원");

  await page.getByRole("button", { name: "추가 지출 계산" }).click();
  const simulator = page.getByRole("dialog", { name: "추가 지출 시뮬레이션" });
  await simulator.getByLabel("추가 지출 항목").fill("가전 비용");
  await simulator.getByLabel("추가로 예상되는 지출").fill("3000000");
  await simulator.getByRole("button", { name: "계산하기" }).click();
  await expect(simulator).toContainText("7,000,000원");
  await expect(simulator).toContainText("원본 자금 계획은 변경되지 않습니다.");

  await page.goto("/chat");
  await page.getByLabel("AI 플래너에게 질문하기").fill("웨딩홀 잔금일이 언제야?");
  await page.getByRole("button", { name: "질문 보내기" }).click();

  await expect(page.getByLabel("AI 플래너 대화")).toContainText("2027-04-30");
  const evidence = page.getByRole("region", { name: "계약 근거" });
  await expect(evidence).toContainText("잔금 20,000,000원은 2027년 4월 30일까지");
  await expect(evidence.getByRole("link", { name: /계약 상세 보기/ })).toHaveAttribute(
    "href",
    /\/contracts\/[0-9a-f-]+/,
  );
});
