const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details ?? {};
  }
}

function toHeaderRecord(headers: HeadersInit | undefined): Record<string, string> {
  if (!headers) {
    return {};
  }
  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }
  return Array.isArray(headers) ? Object.fromEntries(headers) : headers;
}

export async function apiClient<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...toHeaderRecord(init?.headers),
    },
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { error?: ApiErrorBody } | null;
    if (payload?.error) {
      throw new ApiError(response.status, payload.error);
    }
    throw new ApiError(response.status, {
      code: "UNKNOWN_ERROR",
      message: "서버와 통신하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
      details: { status: response.status },
    });
  }

  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}
