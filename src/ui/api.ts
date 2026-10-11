export type Role = "candidate" | "employer";
export interface Session {
  role: Role;
  token: string;
  id: number;
  fspId?: string | null;
  /** true: opened via the prepared demo accounts, not a registered user. */
  demo?: boolean;
}

const KEY = "fsp.session";

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}
export function saveSession(s: Session | null): void {
  try {
    if (s) localStorage.setItem(KEY, JSON.stringify(s));
    else localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: the app still works for this page load */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const e = d as { loc?: unknown[]; msg?: string };
        return `${(e.loc ?? []).slice(1).join(".")}: ${e.msg ?? "invalid"}`;
      })
      .join("; ");
  }
  return "Неизвестная ошибка";
}

export async function api<T>(
  path: string,
  opts: { method?: string; body?: unknown; token?: string } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["content-type"] = "application/json";
  if (opts.token) headers.authorization = `Bearer ${opts.token}`;
  const res = await fetch(path, {
    method: opts.method ?? (opts.body !== undefined ? "POST" : "GET"),
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (res.status === 401 && opts.token) {
    window.dispatchEvent(new Event("fsp:unauthorized"));  // сессия истекла: приложение вернёт на экран входа
  }
  if (!res.ok) {
    throw new ApiError(res.status, describe((data as { detail?: unknown } | null)?.detail));
  }
  return data as T;
}
