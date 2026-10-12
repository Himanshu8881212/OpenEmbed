import { auth, require_ } from "@/lib/auth";
import { tx } from "@/lib/db";
import { route } from "@/lib/http";
import { GIB, gibMonthToDate, monthTotals, plan, storage } from "@/lib/usage";

/** Storage by category and this month's indexing/query use against plan allowances. */
export const GET = route(async (req) => {
  const p = await auth(req);
  require_(p, "usage");
  return tx(p.workspaceId, async (db) => {
    const s = await storage(db), t = await monthTotals(db), pl = await plan(db);
    const index = (t.index_text_tokens ?? 0) + (t.index_media_tokens ?? 0);
    const query = (t.query_text_tokens ?? 0) + (t.query_media_tokens ?? 0);
    const pct = (a: number, b: number) => Math.round((a / b) * 1000) / 10;
    const warnings = [
      ...(pct(s.total_bytes, pl.limits.storage_bytes) >= 80 ? ["storage above 80% of allowance"] : []),
      ...(pct(index, pl.limits.index_tokens_month) >= 80 ? ["indexing above 80% of monthly allowance"] : []),
      ...(pct(query, pl.limits.query_tokens_month) >= 80 ? ["queries above 80% of monthly allowance"] : []),
    ];
    return {
      period: { start: new Date(Date.UTC(new Date().getUTCFullYear(), new Date().getUTCMonth(), 1)).toISOString() },
      storage: { ...s, total_gib: s.total_bytes / GIB, gib_month_to_date: await gibMonthToDate(db, s.total_bytes), limit_bytes: pl.limits.storage_bytes, remaining_bytes: Math.max(0, pl.limits.storage_bytes - s.total_bytes) },
      indexing: { text_tokens: t.index_text_tokens ?? 0, media_tokens: t.index_media_tokens ?? 0, total_tokens: index, limit_tokens: pl.limits.index_tokens_month, remaining_tokens: Math.max(0, pl.limits.index_tokens_month - index) },
      queries: { text_tokens: t.query_text_tokens ?? 0, media_tokens: t.query_media_tokens ?? 0, total_tokens: query, limit_tokens: pl.limits.query_tokens_month, remaining_tokens: Math.max(0, pl.limits.query_tokens_month - query) },
      hard_caps: !pl.allow_excess, warnings,
      units: { storage: "bytes (GiB = 1073741824 bytes); gib_month_to_date = time-weighted GiB / month length (hourly samples)", tokens: "measured EmbeddingGemma 2 model tokens; media tokens per model card rates" },
    };
  });
});
