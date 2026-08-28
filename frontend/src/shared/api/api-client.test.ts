import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { ApiError, apiClient } from "./api-client";

const baseUrl = "http://localhost:8000/api";

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

describe("apiClient", () => {
  it("returns undefined for a 204 No Content success response instead of throwing", async () => {
    server.use(
      http.delete(`${baseUrl}/documents/1`, () => new HttpResponse(null, { status: 204 })),
    );

    await expect(apiClient("/documents/1", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("parses a normal JSON success response", async () => {
    server.use(http.get(`${baseUrl}/health`, () => HttpResponse.json({ status: "ok" })));

    await expect(apiClient("/health")).resolves.toEqual({ status: "ok" });
  });

  it("throws ApiError with the backend's error body on failure", async () => {
    server.use(
      http.post(`${baseUrl}/documents`, () =>
        HttpResponse.json(
          {
            error: {
              code: "UNSUPPORTED_MEDIA_TYPE",
              message: "PDF, JPG, PNG 파일만 업로드할 수 있습니다.",
            },
          },
          { status: 415 },
        ),
      ),
    );

    await expect(apiClient("/documents", { method: "POST" })).rejects.toMatchObject({
      status: 415,
      code: "UNSUPPORTED_MEDIA_TYPE",
      message: "PDF, JPG, PNG 파일만 업로드할 수 있습니다.",
    } satisfies Partial<ApiError>);
  });

  it("falls back to a Korean message when a non-JSON failure body is returned", async () => {
    server.use(
      http.get(`${baseUrl}/health`, () => new HttpResponse("Bad Gateway", { status: 502 })),
    );

    await expect(apiClient("/health")).rejects.toMatchObject({
      status: 502,
      code: "UNKNOWN_ERROR",
      message: "서버와 통신하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
    } satisfies Partial<ApiError>);
  });
});
