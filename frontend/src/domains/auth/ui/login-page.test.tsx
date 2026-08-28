import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { DEMO_SESSION_STORAGE_KEY, DemoSessionProvider } from "../model/auth-context";
import { LoginPage } from "./login-page";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

const loginUrl = "http://localhost:8000/api/v1/auth/demo-login";
const demoResponse = {
  user: {
    id: "00000000-0000-0000-0000-000000000001",
    loginId: "demo",
    displayName: "Demo User",
    email: null,
  },
  mode: "DEMO" as const,
};

const server = setupServer(
  http.post(loginUrl, async ({ request }) => {
    expect(await request.text()).toBe("");
    return HttpResponse.json(demoResponse);
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

beforeEach(() => {
  replace.mockReset();
  window.sessionStorage.clear();
});

function renderLoginPage() {
  return render(
    <DemoSessionProvider>
      <LoginPage />
    </DemoSessionProvider>,
  );
}

describe("LoginPage", () => {
  it("renders the demo login introduction and button", async () => {
    renderLoginPage();

    expect(screen.getByRole("heading", { name: "우리의 결혼 준비를 한곳에서" })).toBeVisible();
    expect(await screen.findByRole("button", { name: "데모 계정으로 시작하기" })).toBeEnabled();
    expect(screen.getByText("Demo Mode")).toBeVisible();
  });

  it("sends one bodyless request, blocks duplicate clicks, and stores only public profile data", async () => {
    let requestCount = 0;
    let resolveRequest: (() => void) | undefined;
    const requestGate = new Promise<void>((resolve) => {
      resolveRequest = resolve;
    });

    server.use(
      http.post(loginUrl, async ({ request }) => {
        requestCount += 1;
        expect(await request.text()).toBe("");
        await requestGate;
        return HttpResponse.json({
          ...demoResponse,
          passwordHash: "must-not-be-stored",
          accessToken: "must-not-be-stored",
        });
      }),
    );

    const user = userEvent.setup();
    renderLoginPage();
    const button = await screen.findByRole("button", { name: "데모 계정으로 시작하기" });

    await user.click(button);
    const pendingButton = screen.getByRole("button", { name: "로그인 중..." });
    expect(pendingButton).toBeDisabled();
    expect(pendingButton).toHaveAttribute("aria-busy", "true");

    await user.click(pendingButton);
    expect(requestCount).toBe(1);

    await act(async () => resolveRequest?.());
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));

    const storedSession = JSON.parse(
      window.sessionStorage.getItem(DEMO_SESSION_STORAGE_KEY) ?? "null",
    ) as Record<string, unknown>;
    expect(storedSession).toEqual(demoResponse);
    expect(storedSession).not.toHaveProperty("passwordHash");
    expect(storedSession).not.toHaveProperty("accessToken");
  });

  it("shows a safe error and allows retry after a failed request", async () => {
    let requestCount = 0;
    server.use(
      http.post(loginUrl, () => {
        requestCount += 1;
        return HttpResponse.json({ error: { code: "INTERNAL_ERROR" } }, { status: 500 });
      }),
    );

    const user = userEvent.setup();
    renderLoginPage();
    await user.click(await screen.findByRole("button", { name: "데모 계정으로 시작하기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "데모 계정으로 로그인하지 못했어요. 잠시 후 다시 시도해 주세요.",
    );
    expect(screen.getByRole("button", { name: "데모 계정으로 시작하기" })).toBeEnabled();

    server.use(
      http.post(loginUrl, () => {
        requestCount += 1;
        return HttpResponse.json(demoResponse);
      }),
    );
    await user.click(screen.getByRole("button", { name: "데모 계정으로 시작하기" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
    expect(requestCount).toBe(2);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("redirects an existing demo session away from the login page", async () => {
    window.sessionStorage.setItem(DEMO_SESSION_STORAGE_KEY, JSON.stringify(demoResponse));

    renderLoginPage();

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  });
});
