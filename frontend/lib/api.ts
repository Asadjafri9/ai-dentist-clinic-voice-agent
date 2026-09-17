const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  code: string;
  status: number;
  retryable: boolean;
  requestId: string;

  constructor(status: number, body: any) {
    super(body?.error?.message ?? `Request failed (${status})`);
    this.code = body?.error?.code ?? "UNKNOWN";
    this.status = status;
    this.retryable = body?.error?.retryable ?? false;
    this.requestId = body?.error?.request_id ?? "";
  }
}

function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)ai_voice_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: unknown } = {}
): Promise<T> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && method !== "HEAD") {
    const token = csrfToken();
    if (token) headers["X-CSRF-Token"] = token;
  }
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    credentials: "include",
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  let body: any = null;
  try {
    body = await res.json();
  } catch {
    // non-JSON
  }
  if (!res.ok) {
    throw new ApiError(res.status, body);
  }
  return (body?.data ?? body) as T;
}

export const get = <T = any>(path: string) => api<T>(path);
export const post = <T = any>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body });
export const patch = <T = any>(path: string, body?: unknown) =>
  api<T>(path, { method: "PATCH", body });
export const del = <T = any>(path: string) => api<T>(path, { method: "DELETE" });
