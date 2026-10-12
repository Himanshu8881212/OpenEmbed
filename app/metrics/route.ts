import { timingSafeEqual } from "node:crypto";
import { pool } from "@/lib/db";
import { LATENCY_BUCKETS, metrics } from "@/lib/http";

export const dynamic = "force-dynamic";
const same = (a: string, b: string) => a.length === b.length && timingSafeEqual(Buffer.from(a), Buffer.from(b));

/** Prometheus exposition. Requires `Authorization: Bearer $KB_METRICS_TOKEN` (unset token = disabled). */
export async function GET(req: Request) {
  const want = process.env.KB_METRICS_TOKEN;
  if (!want || !same(req.headers.get("authorization") ?? "", `Bearer ${want}`)) return new Response("not found\n", { status: 404 });
  const out: string[] = ["# TYPE kb_http_requests_total counter"];
  for (const [k, v] of metrics.requests) { const [m, r, s] = k.split(" "); out.push(`kb_http_requests_total{method="${m}",route="${r}",status="${s}"} ${v}`); }
  out.push("# TYPE kb_http_request_duration_seconds histogram");
  for (const [k, b] of metrics.latency) {
    const [m, r] = k.split(" "), l = `method="${m}",route="${r}"`;
    LATENCY_BUCKETS.forEach((le, i) => out.push(`kb_http_request_duration_seconds_bucket{${l},le="${le}"} ${b[i]}`));
    out.push(`kb_http_request_duration_seconds_bucket{${l},le="+Inf"} ${b[LATENCY_BUCKETS.length]}`, `kb_http_request_duration_seconds_count{${l}} ${b[LATENCY_BUCKETS.length]}`, `kb_http_request_duration_seconds_sum{${l}} ${b[LATENCY_BUCKETS.length + 1].toFixed(6)}`);
  }
  const { rows } = await pool.query("SELECT * FROM kb_metrics()");
  const seen = new Set<string>();
  for (const r of rows) { if (!seen.has(r.name)) { out.push(`# TYPE ${r.name} gauge`); seen.add(r.name); } out.push(`${r.name}${r.labels ? `{${r.labels}}` : ""} ${r.value}`); }
  return new Response(out.join("\n") + "\n", { headers: { "content-type": "text/plain; version=0.0.4" } });
}
