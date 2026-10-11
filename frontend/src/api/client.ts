import { IS_HOSTED } from "../config/runtime";

let cachedToken: string | null = null;

export class ApiRequestError extends Error {
  constructor(message: string, readonly code?: string) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function initApiToken(): Promise<string> {
  if (IS_HOSTED) {
    return "";
  }
  if (cachedToken) return cachedToken;
  const response = await fetch("/api/auth/token");
  if (!response.ok) {
    throw new Error("No se pudo iniciar la sesión local de la API.");
  }
  const data = (await response.json()) as { token: string };
  cachedToken = data.token;
  const { setApiToken: setTopicTransferToken } = await import("./topicTransfer");
  setTopicTransferToken(data.token);
  return data.token;
}

export function getApiToken(): string | null {
  return cachedToken;
}

export async function apiFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!IS_HOSTED) {
    const token = cachedToken ?? (await initApiToken());
    headers.set("X-LearnUp-Token", token);
  }
  return fetch(input, { ...init, headers });
}

export async function apiJson<T>(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<T> {
  const response = await apiFetch(input, init);
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string | { code?: string; message?: string };
      code?: string;
    } | null;
    const detail = body?.detail;
    const message = typeof detail === "string" ? detail : detail?.message;
    const code = body?.code ?? (typeof detail === "object" ? detail?.code : undefined);
    throw new ApiRequestError(message ?? `Error HTTP ${response.status}`, code);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
