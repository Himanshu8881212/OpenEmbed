import { auth, require_, storeFilter } from "@/lib/auth";
import { all, tx } from "@/lib/db";
import { page, paged, route } from "@/lib/http";
import { jobJson } from "@/lib/jobs";

export const GET = route(async (req) => {
  const p = await auth(req);
  require_(p, "source:read");
  const { limit, after } = page(req);
  const u = req.nextUrl.searchParams;
  return tx(p.workspaceId, async (db) => {
    const rows = await all(db, `SELECT * FROM jobs WHERE ($1::uuid[] IS NULL OR store_id = ANY($1)) AND ($2::uuid IS NULL OR store_id = $2) AND ($3::text IS NULL OR state = $3)
        AND ($4::timestamptz IS NULL OR (created_at, id) < ($4, $5::uuid)) ORDER BY created_at DESC, id DESC LIMIT $6`,
      [storeFilter(p), u.get("store_id"), u.get("state"), after?.[0] ?? null, after?.[1] ?? null, limit + 1]);
    const out = paged(rows, limit);
    out.data = await Promise.all(out.data.map((j) => jobJson(db, j)));
    return out;
  });
});
