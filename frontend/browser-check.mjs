import assert from "node:assert/strict";
import process from "node:process";

import { chromium } from "@playwright/test";

let browser;

(async () => {
  const baseUrl = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const requests = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/chat")) {
      requests.push(request.postDataJSON());
    }
  });

  await page.goto(new URL("/login", baseUrl).href);
  await page.getByRole("button", { name: "데모 계정으로 시작하기" }).click();
  await page.waitForURL((url) => url.pathname !== "/login");
  await page.goto(new URL("/chat", baseUrl).href);
  await page.evaluate(() => localStorage.removeItem("mairry.chat.conversationId"));
  await page.reload();
  const input = page.getByLabel("AI 플래너에게 질문하기");
  await input.waitFor({ state: "visible" });
  await page.locator(".chat-message.assistant").first().waitFor({ state: "visible" });

  async function ask(question) {
    const assistants = page.locator(".chat-message.assistant");
    const before = await assistants.count();
    await input.fill(question);
    await page.getByRole("button", { name: "질문 보내기" }).click();
    await assistants.nth(before).waitFor({ state: "visible", timeout: 60_000 });
    await page.waitForFunction(
      (index) => {
        const message = document.querySelectorAll(".chat-message.assistant").item(index);
        return message.textContent && !message.textContent.includes("확인하고 있습니다.");
      },
      before,
      { timeout: 60_000 },
    );
    return assistants.nth(before).innerText();
  }

  const hello = await ask("안녕");
  assert.match(hello, /안녕하세요/);
  assert.equal(await page.getByText("확인 가능한 계약 또는 계산 근거가 없습니다.").count(), 0);

  await page.getByRole("button", { name: "새 질문" }).click();
  const simulation = await ask("가전제품 구매로 300만 원 쓰면 얼마 남아?");
  assert.match(simulation, /21,000,000원/);
  const followUp = await ask("그럼 300만원 써도 되는 거야?");
  assert.match(followUp, /예산 부족 상태는 아니/);
  assert.ok(requests.at(-1).conversationId);
  assert.equal(requests.at(-2).conversationId, undefined);

  await page.getByRole("button", { name: "새 질문" }).click();
  const contractDetails = await ask("그랜드볼룸 웨딩홀 계약 내용 알려줘");
  assert.doesNotMatch(contractDetails, /계약, 지급 일정 또는 자금계획에 대해 질문/);
  const contractDetailsCitationCount = await page.locator(".chat-citation").count();

  await page.screenshot({ path: "../test-results/chat-regression.png", fullPage: true });
  process.stdout.write(
    JSON.stringify(
      {
        hello,
        simulation,
        followUp,
        contractDetailsCitationCount,
        followUpConversationId: requests.at(-2).conversationId,
      },
      null,
      2,
    ),
  );
  await browser.close();
})().catch(async (error) => {
  console.error(error);
  await browser?.close();
  process.exitCode = 1;
});
