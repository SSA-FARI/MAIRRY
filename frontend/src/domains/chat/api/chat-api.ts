import { apiClient } from "@/shared/api/api-client";
import type { ChatResponse } from "../model/types";

export function sendChatMessage(message: string, signal?: AbortSignal): Promise<ChatResponse> {
  return apiClient<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
    signal,
  });
}
