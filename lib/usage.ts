import { Plan } from "./config";
import { one, type Db } from "./db";
import { ApiError } from "./http";

export const GIB = 1073741824;
const VECTOR_BYTES = 768 * 4;

/** Storage by category. Reused physical bytes count once per workspace (blobs are content-addressed). */
export async function storage(db: Db) {
  const r = await one(db, `SELECT
      (SELECT coalesce(sum(size),0) FROM blobs)::bigint AS originals,
      (SELECT coalesce(sum(octet_length(coalesce(content,''))),0) FROM segments)::bigint AS prepared_text,
      (SELECT count(*) FROM segments)::bigint AS vectors,
      (SELECT coalesce(sum(octet_length(metadata::text)),0) FROM files)::bigint AS metadata`);
  const s = { originals_bytes: Number(r.originals), prepared_bytes: Number(r.prepared_text), vector_bytes: Number(r.vectors) * VECTOR_BYTES, metadata_bytes: Number(r.metadata) };
  return { ...s, total_bytes: s.originals_bytes + s.prepared_bytes + s.vector_bytes + s.metadata_bytes };
}

/** GiB-month accrued this month: step integral of hourly samples (and the current size up to now) over the month length. */
export async function gibMonthToDate(db: Db, currentBytes: number) {
  const r = await one(db, `WITH m AS (SELECT date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' s),
      pts AS (SELECT greatest(at, (SELECT s FROM m)) t, bytes FROM storage_samples WHERE at >= (SELECT s FROM m) - interval '1 hour'
              UNION ALL SELECT now(), $1::bigint),
      seg AS (SELECT t, bytes, lead(t) OVER (ORDER BY t) nt FROM pts)
    SELECT coalesce(sum(bytes::numeric * extract(epoch FROM nt - t)), 0) byte_seconds,
           extract(epoch FROM ((SELECT s FROM m) + interval '1 month') - (SELECT s FROM m)) month_seconds FROM seg WHERE nt IS NOT NULL`, [currentBytes]);
  return Number(r.byte_seconds) / GIB / Number(r.month_seconds);
}

export async function monthTotals(db: Db) {
  const rows = (await db.query(`SELECT kind, sum(quantity)::bigint q FROM usage_events WHERE created_at >= date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' GROUP BY kind`)).rows;
  const t: Record<string, number> = {};
  for (const r of rows) t[r.kind] = Number(r.q);
  return t;
}

export async function plan(db: Db): Promise<Plan> {
  return Plan.parse((await one(db, "SELECT plan FROM workspaces WHERE id = kb_ws()")).plan);
}

/** Hard caps (default when excess is not enabled). Throws 429 QUOTA_EXCEEDED. */
export async function enforce(db: Db, what: "storage" | "query", add = 0) {
  const p = await plan(db);
  if (p.allow_excess) return;
  if (what === "storage") {
    const s = await storage(db);
    if (s.total_bytes + add > p.limits.storage_bytes) throw new ApiError(429, "QUOTA_EXCEEDED", "Storage allowance exhausted for this plan");
  } else {
    const t = await monthTotals(db);
    if ((t.query_text_tokens ?? 0) + (t.query_media_tokens ?? 0) + add > p.limits.query_tokens_month) throw new ApiError(429, "QUOTA_EXCEEDED", "Query allowance exhausted for this plan");
  }
}

/** Provider-controlled plan features (e.g. `custom_profiles`), off unless the plan enables them. */
export async function requireFeature(db: Db, feature: string) {
  const r = await one(db, "SELECT coalesce((plan->'features'->>$1)::boolean, false) AS on FROM workspaces WHERE id = kb_ws()", [feature]);
  if (!r?.on) throw new ApiError(403, "FEATURE_DISABLED", `'${feature}' is not enabled for this workspace's plan. Chunking is managed by the provider.`);
}

export const record = (db: Db, kind: string, quantity: number, idem: string) =>
  db.query("INSERT INTO usage_events (workspace_id, kind, quantity, idem_key) VALUES (kb_ws(), $1, $2, $3) ON CONFLICT DO NOTHING", [kind, quantity, idem]);
