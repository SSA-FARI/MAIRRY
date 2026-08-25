import { apiClient } from "@/shared/api/api-client";
import type { FinanceSummary } from "../model/types";

export function getFinanceSummary(): Promise<FinanceSummary> {
  return apiClient<FinanceSummary>("/finance/summary");
}

