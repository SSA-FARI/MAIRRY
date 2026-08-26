import assert from "node:assert/strict";
import test from "node:test";

test("creates inline comments only for validated Critical and Major findings", async () => {
  process.env.GEMINI_API_KEY = "test-key";
  process.env.GITHUB_TOKEN = "test-token";
  process.env.GITHUB_REPOSITORY = "test-owner/test-repository";
  process.env.PR_NUMBER = "1";

  const originalFetch = globalThis.fetch;
  let issueCommentBody = null;
  let inlineReviewRequest = null;
  const diff = `diff --git a/example.js b/example.js
--- a/example.js
+++ b/example.js
@@ -1 +1,2 @@
 existing();
+changed();
`;
  const geminiReview = {
    summary: "변경 사항에서 한 가지 주요 문제를 발견했습니다.",
    findings: [
      {
        severity: "Critical",
        path: "example.js",
        line: 2,
        title: "검증되지 않은 변경",
        description: "변경값을 검증하지 않습니다.",
        risk: "잘못된 값이 저장될 수 있습니다.",
        fix: "저장 전에 값을 검증하세요.",
        test: "잘못된 값 거부 테스트를 추가하세요.",
      },
      {
        severity: "Minor",
        path: "example.js",
        line: 2,
        title: "경계 테스트 누락",
        description: "경계값 테스트가 없습니다.",
        risk: "회귀를 놓칠 수 있습니다.",
        fix: "경계값 테스트를 추가하세요.",
        test: "최솟값과 최댓값을 검증하세요.",
      },
    ],
  };

  function jsonResponse(value, status = 200) {
    return new Response(JSON.stringify(value), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }

  globalThis.fetch = async (url, init = {}) => {
    const requestUrl = String(url);
    const method = init.method ?? "GET";

    if (requestUrl.includes("generativelanguage.googleapis.com")) {
      return jsonResponse({
        status: "completed",
        steps: [
          {
            type: "model_output",
            content: [{ type: "text", text: JSON.stringify(geminiReview) }],
          },
        ],
      });
    }
    if (requestUrl.endsWith("/pulls/1") && init.headers?.Accept === "application/vnd.github.diff") {
      return new Response(diff, { status: 200 });
    }
    if (requestUrl.endsWith("/pulls/1") && method === "GET") {
      return jsonResponse({ head: { sha: "test-head-sha" } });
    }
    if (requestUrl.includes("/issues/1/comments") && method === "GET") {
      return jsonResponse(
        issueCommentBody
          ? [{ id: 10, user: { login: "github-actions[bot]" }, body: issueCommentBody }]
          : [],
      );
    }
    if (requestUrl.includes("/issues/1/comments") && method === "POST") {
      issueCommentBody = JSON.parse(init.body).body;
      return jsonResponse({ id: 10 });
    }
    if (requestUrl.endsWith("/issues/comments/10") && method === "PATCH") {
      issueCommentBody = JSON.parse(init.body).body;
      return jsonResponse({ id: 10 });
    }
    if (requestUrl.includes("/pulls/1/reviews") && method === "GET") {
      return jsonResponse([]);
    }
    if (requestUrl.endsWith("/pulls/1/reviews") && method === "POST") {
      inlineReviewRequest = JSON.parse(init.body);
      return jsonResponse({ id: 20 });
    }

    throw new Error(`Unexpected request: ${method} ${requestUrl}`);
  };

  try {
    await import(`./review-pr.mjs?test=${Date.now()}`);
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(inlineReviewRequest.comments.length, 1);
  assert.equal(inlineReviewRequest.comments[0].path, "example.js");
  assert.equal(inlineReviewRequest.comments[0].line, 2);
  assert.match(inlineReviewRequest.comments[0].body, /\[Critical\]/);
  assert.match(issueCommentBody, /경계 테스트 누락/);
  assert.match(issueCommentBody, /코드 라인에 등록됨/);
});
