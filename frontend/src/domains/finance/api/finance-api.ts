import { apiClient } from "@/shared/api/api-client";
import type { FinanceSummary, SimulationRequest, SimulationResult } from "../model/types";

export function getFinanceSummary(signal?: AbortSignal): Promise<FinanceSummary> {
  return apiClient<FinanceSummary>("/finance/summary", { signal });
}

export function simulateAdditionalExpense(payload: SimulationRequest): Promise<SimulationResult> {
  return apiClient<SimulationResult>("/finance/simulate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
