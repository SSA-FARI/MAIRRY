const assert = require("node:assert/strict");
const { chromium } = require("@playwright/test");

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const requests = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/chat")) {
      requests.push(request.postDataJSON());
    }
  });

  await page.goto("http://localhost:3000/chat");
  await page.evaluate(() => localStorage.removeItem("mairry.chat.conversationId"));
  await page.reload();
  const input = page.getByLabel("AI 플래너에게 질문하기");

  async function ask(question) {
    const assistants = page.locator(".chat-message.assistant");
    const before = await assistants.count();
    await input.fill(question);
    await page.getByRole("button", { name: "질문 보내기" }).click();
    await assistants.nth(before).waitFor({ state: "visible", timeout: 60_000 });
    return assistants.nth(before).innerText();
  }

  const hello = await ask("안녕");
  assert.match(hello, /안녕하세요/);
  assert.equal(
    await page.getByText("확인 가능한 계약 또는 계산 근거가 없습니다.").count(),
    0,
  );

  await page.getByRole("button", { name: "새 질문" }).click();
  const simulation = await ask("가전제품 구매로 300만 원 쓰면 얼마 남아?");
  assert.match(simulation, /21,000,000원/);
  const followUp = await ask("그럼 300만원 써도 되는 거야?");
  assert.match(followUp, /예산 부족 상태는 아니/);
  assert.ok(requests.at(-1).conversationId);
  assert.equal(requests.at(-2).conversationId, undefined);

  await page.getByRole("button", { name: "새 질문" }).click();
  const cancellation = await ask("웨딩홀 취소 조건 알려줘");
  assert.doesNotMatch(cancellation, /계약, 지급 일정 또는 자금계획에 대해 질문/);
  assert.ok(await page.locator(".chat-citation").count());

  await page.screenshot({ path: "../test-results/chat-regression.png", fullPage: true });
  process.stdout.write(
    JSON.stringify(
      {
        hello,
        simulation,
        followUp,
        cancellationHasCitation: true,
        followUpConversationId: requests.at(-2).conversationId,
      },
      null,
      2,
    ),
  );
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
