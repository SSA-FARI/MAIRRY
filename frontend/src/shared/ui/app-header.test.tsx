import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppHeader } from "./app-header";
import { StatusBadge } from "./status-badge";

describe("shared UI", () => {
  it("marks only the active navigation item as the current page", () => {
    render(<AppHeader active="contracts" displayName="마리" />);
    expect(screen.getByRole("link", { name: "계약 관리" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "금융 대시보드" })).not.toHaveAttribute("aria-current");
    expect(screen.getByText("DEMO · 마리")).toBeVisible();
  });

  it("exposes status text as well as its visual tone", () => {
    render(<StatusBadge tone="warning">확인 필요</StatusBadge>);
    expect(screen.getByText("확인 필요")).toHaveClass("status-badge-warning");
  });
});
