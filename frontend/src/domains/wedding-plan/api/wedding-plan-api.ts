import { apiClient } from "@/shared/api/api-client";
import type { WeddingPlan, WeddingPlanUpsert } from "../model/types";

export function getWeddingPlan(signal?: AbortSignal): Promise<WeddingPlan> {
  return apiClient<WeddingPlan>("/wedding-plan", { signal });
}

export function saveWeddingPlan(payload: WeddingPlanUpsert): Promise<WeddingPlan> {
  return apiClient<WeddingPlan>("/wedding-plan", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
