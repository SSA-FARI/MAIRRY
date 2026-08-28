import { render, screen, waitFor } from "@testing-library/react";
import { DashboardPage } from "@/domains/finance";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DEMO_SESSION_STORAGE_KEY, DemoSessionProvider } from "../model/auth-context";
import { AuthGuard } from "./auth-guard";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

const demoSession = {
  user: {
    id: "00000000-0000-0000-0000-000000000001",
    loginId: "demo",
    displayName: "Demo User",
    email: null,
  },
  mode: "DEMO",
};

beforeEach(() => {
  replace.mockReset();
  window.sessionStorage.clear();
});

function renderGuard() {
  return render(
    <DemoSessionProvider>
      <AuthGuard>
        <DashboardPage />
      </AuthGuard>
    </DemoSessionProvider>,
  );
}

describe("AuthGuard", () => {
  it("redirects to login when no demo session exists", async () => {
    renderGuard();

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByRole("heading", { name: "우리 결혼 자금 현황" })).not.toBeInTheDocument();
  });

  it("allows dashboard access when a demo session exists", async () => {
    window.sessionStorage.setItem(DEMO_SESSION_STORAGE_KEY, JSON.stringify(demoSession));

    renderGuard();

    expect(await screen.findByRole("heading", { name: "우리 결혼 자금 현황" })).toBeVisible();
    expect(screen.getByText("Demo User님, 반가워요.")).toBeVisible();
    expect(replace).not.toHaveBeenCalledWith("/login");
  });
});
