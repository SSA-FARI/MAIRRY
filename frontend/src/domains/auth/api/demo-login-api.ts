import { apiClient } from "@/shared/api/api-client";
import type { DemoSession } from "../model/types";

export function demoLogin(): Promise<DemoSession> {
  return apiClient<DemoSession>("/v1/auth/demo-login", { method: "POST" });
}
