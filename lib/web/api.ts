"use client";
import { accessToken } from "./session";

export class ApiErr extends Error { code: string; status: number; requestId?: string; constructor(status: number, code: string, message: string, requestId?: string) { super(message); this.status = status; this.code = code; this.requestId = requestId; } }

export const workspace = { get: () => (typeof window === "undefined" ? null : localStorage.getItem("kb.workspace")), set: (id: string) => localStorage.setItem("kb.workspace", id) };

/** Calls the same /v1 business API as the CLI, with the signed-in user's short-lived token. */
export async function call<T = any>(method: string, path: string, body?: unknown, opts: { raw?: BodyInit; headers?: Record<string, string> } = {}): Promise<T> {
  const tok = await accessToken();
  if (!tok) throw new ApiErr(401, "AUTHENTICATION_REQUIRED", "Your session ended. Sign in again.");
  const headers: Record<string, string> = { authorization: `Bearer ${tok}`, ...(opts.headers ?? {}) };
  const ws = workspace.get();
  if (ws && !path.startsWith("/v1/workspaces") && path !== "/v1/me") headers["x-workspace-id"] = ws;
  if (body !== undefined) headers["content-type"] = "application/json";
  let r: Response;
  try { r = await fetch(path, { method, headers, body: opts.raw ?? (body !== undefined ? JSON.stringify(body) : undefined) }); }
  catch { throw new ApiErr(0, "NETWORK", "The service could not be reached. Check your connection and try again."); }
  if (r.status === 204) return null as T;
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiErr(r.status, j.error?.code ?? "ERROR", j.error?.message ?? r.statusText, j.error?.request_id);
  return j;
}

export async function sha256Hex(blob: Blob) {
  // ponytail: hashes the whole file in memory; stream in chunks if browser imports above ~1 GiB are needed.
  const d = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export const fmtBytes = (n: number) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KiB` : n < 1073741824 ? `${(n / 1048576).toFixed(1)} MiB` : `${(n / 1073741824).toFixed(2)} GiB`);
