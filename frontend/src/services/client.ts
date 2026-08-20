/**
 * HTTP client.
 *
 * Three responsibilities and no more: attach the session identity, unwrap the
 * single error envelope from docs/API_CONTRACT.md, and let a build flag swap in
 * local fixtures so the UI can be built ahead of an endpoint.
 */

import { uuid4 } from "@/lib/utils";
import { useAppStore } from "@/store/useAppStore";
import type { ApiErrorBody, ErrorCode } from "@/types/api";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
// A build-time default for a deployed demo; the admin page also lets the
// operator paste a token at runtime (there is no login, per ADR-005), which
// takes priority since it is what the person looking at the screen typed.
const ENV_ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN ?? "";
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";

const SESSION_KEY = "smartbuy.session_id";

/**
 * The client mints the session id, per the contract. It lives in localStorage
 * so a refresh mid-demo rejoins the same conversation instead of starting over.
 */
export function sessionId(): string {
  try {
    const existing = window.localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const minted = uuid4();
    window.localStorage.setItem(SESSION_KEY, minted);
    return minted;
  } catch {
    // Private mode with storage disabled: fall back to a per-tab identity.
    return uuid4();
  }
}

export function resetSession(): string {
  const minted = uuid4();
  try {
    window.localStorage.setItem(SESSION_KEY, minted);
  } catch {
    /* nothing to do — the caller still gets a fresh id */
  }
  return minted;
}

/**
 * Adopt an existing identity — how "signing in" works here.
 *
 * There is no authentication in this project (ADR-005): the session id *is*
 * the user id, so switching it switches whose history and whose personalised
 * offer you see. That is fine for a demo over synthetic shoppers and would be
 * indefensible over real accounts, which is exactly why the roster endpoint
 * only ever returns seeded rows.
 */
export function adoptSession(id: string): void {
  try {
    window.localStorage.setItem(SESSION_KEY, id);
  } catch {
    /* storage disabled: the switch simply will not survive a refresh */
  }
}

export class ApiError extends Error {
  readonly code: ErrorCode;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(code: ErrorCode, message: string, status: number, details = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }

  /** Retrying a validation failure just fails again. */
  get retryable(): boolean {
    return this.status >= 500 || this.status === 0 || this.code === "RATE_LIMITED";
  }
}

function query(params?: Record<string, unknown>): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  params?: Record<string, unknown>;
  admin?: boolean;
  signal?: AbortSignal;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, params, admin = false, signal } = options;

  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Session-Id": sessionId(),
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (admin) {
    const token = useAppStore.getState().adminToken || ENV_ADMIN_TOKEN;
    if (token) headers["X-Admin-Token"] = token;
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}${query(params)}`, {
      method,
      headers,
      signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (cause) {
    // The server is down or the network dropped. Status 0 marks it retryable.
    throw new ApiError(
      "INTERNAL_ERROR",
      "Could not reach the SmartBuy service. Is the backend running?",
      0,
      { cause: String(cause) },
    );
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const envelope = payload as ApiErrorBody | null;
    const error = envelope?.error;
    throw new ApiError(
      error?.code ?? "INTERNAL_ERROR",
      error?.message ?? `Request failed with status ${response.status}.`,
      response.status,
      error?.details ?? {},
    );
  }

  return payload as T;
}

export const http = {
  get: <T>(path: string, params?: Record<string, unknown>, admin = false) =>
    request<T>(path, { method: "GET", params, admin }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
};
