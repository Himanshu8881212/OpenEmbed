import { randomUUID } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public param?: string, public headers: Record<string, string> = {}) { super(message); }
}

// In-process HTTP metrics (exported at /metrics). Per API instance; Prometheus aggregates across instances.
const g = globalThis as unknown as { kbMetrics?: { requests: Map<string, number>; latency: Map<string, number[]> } };
export const metrics = (g.kbMetrics ??= { requests: new Map(), latency: new Map() });
export const LATENCY_BUCKETS = [0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10];
function observe(method: string, routeKey: string, status: number, seconds: number) {
  const k = `${method} ${routeKey} ${status}`;
  metrics.requests.set(k, (metrics.requests.get(k) ?? 0) + 1);
  const lk = `${method} ${routeKey}`;
  const b = metrics.latency.get(lk) ?? new Array(LATENCY_BUCKETS.length + 2).fill(0); // buckets…, +Inf, sum
  LATENCY_BUCKETS.forEach((le, i) => { if (seconds <= le) b[i]++; });
  b[LATENCY_BUCKETS.length]++;
  b[LATENCY_BUCKETS.length + 1] += seconds;
  metrics.latency.set(lk, b);
}
export const notFound = (what = "Resource") => new ApiError(404, "RESOURCE_NOT_FOUND", `${what} not found`);
export const denied = (msg = "The identity lacks permission for this operation") => new ApiError(403, "ACCESS_DENIED", msg);
export const invalid = (msg: string, param?: string) => new ApiError(400, "INVALID_REQUEST", msg, param);

type Ctx = { params: Promise<Record<string, string>> };
export type Handler = (req: NextRequest, p: Record<string, string>, requestId: string) => Promise<Response | unknown>;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Wraps a route: request id, JSON responses, uniform error envelope. `openai` selects the OpenAI-style envelope. */
export function route(fn: Handler, opts: { openai?: boolean } = {}) {
  return async (req: NextRequest, ctx: Ctx) => {
    const requestId = "req_" + randomUUID().replaceAll("-", "");
    const started = performance.now();
    let res: Response;
    try {
      const params = ctx?.params ? await ctx.params : {};
      for (const [k, v] of Object.entries(params)) if (k.endsWith("id") && !UUID.test(v)) throw notFound();
      const out = await fn(req, params, requestId);
      res = out instanceof Response ? out : NextResponse.json(out);
    } catch (e) {
      res = errorResponse(e, requestId, opts.openai);
    }
    res.headers.set("x-request-id", requestId);
    // route pattern (ids replaced) keeps metrics low-cardinality and logs free of identifiers beyond the request id
    const routeKey = req.nextUrl.pathname.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, ":id").replace(/\/parts\/\d+$/, "/parts/:n");
    const secs = (performance.now() - started) / 1000;
    observe(req.method, routeKey, res.status, secs);
    if (process.env.KB_ACCESS_LOG !== "0") console.log(JSON.stringify({ ts: new Date().toISOString(), level: "info", msg: "request", request_id: requestId, method: req.method, route: routeKey, status: res.status, ms: Math.round(secs * 1000) }));
    return res;
  };
}

function errorResponse(e: unknown, requestId: string, openai = false) {
  let err: ApiError;
  if (e instanceof ApiError) err = e;
  else if (e instanceof z.ZodError) {
    const i = e.issues[0];
    err = invalid(`${i.path.join(".") || "body"}: ${i.message}`, i.path.join(".") || undefined);
  } else if ((e as any)?.code === "22P02") err = notFound(); // malformed uuid in a nested reference
  else {
    console.error(JSON.stringify({ level: "error", request_id: requestId, error: String((e as any)?.message ?? e).slice(0, 300) }));
    err = new ApiError(500, "INTERNAL_ERROR", "Internal error");
  }
  const body = openai
    ? { error: { message: err.message, type: err.status >= 500 ? "server_error" : err.status === 401 ? "authentication_error" : err.status === 429 ? "rate_limit_error" : "invalid_request_error", param: err.param ?? null, code: err.code.toLowerCase() } }
    : { error: { code: err.code, message: err.message, request_id: requestId, ...(err.param ? { param: err.param } : {}) } };
  return NextResponse.json(body, { status: err.status, headers: err.headers });
}

export async function body<T extends z.ZodTypeAny>(req: NextRequest, schema: T): Promise<z.infer<T>> {
  let raw: unknown;
  try { raw = await req.json(); } catch { throw invalid("Body must be valid JSON"); }
  return schema.parse(raw);
}

export const accepted = (job: { id: string; state: string }) =>
  NextResponse.json({ job_id: job.id, state: job.state, status_url: `/v1/jobs/${job.id}` }, { status: 202 });

/** Cursor pagination over (created_at, id) descending. */
export function page(req: NextRequest) {
  const u = req.nextUrl.searchParams;
  const limit = Math.min(Math.max(Number(u.get("limit") ?? 50) || 50, 1), 200);
  const c = u.get("cursor");
  let after: [string, string] | null = null;
  if (c) {
    try { after = JSON.parse(Buffer.from(c, "base64url").toString()); } catch { throw invalid("Invalid cursor", "cursor"); }
    if (!Array.isArray(after) || after.length !== 2) throw invalid("Invalid cursor", "cursor");
  }
  return { limit, after };
}
export function paged<T extends { created_at: string | Date; id: string | number }>(rows: T[], limit: number, map: (r: T) => unknown = (r) => r) {
  const more = rows.length > limit;
  const data = rows.slice(0, limit);
  const last = data[data.length - 1];
  return {
    data: data.map(map),
    // exact database timestamp (microseconds), never a millisecond-rounded Date
    next_cursor: more && last ? Buffer.from(JSON.stringify([String(last.created_at), String(last.id)])).toString("base64url") : null,
  };
}
export const iso = (d: Date | string | null | undefined) => (d ? new Date(d).toISOString() : null);
