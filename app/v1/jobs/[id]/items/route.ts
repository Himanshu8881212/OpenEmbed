import { auth, require_ } from "@/lib/auth";
import { all, tx } from "@/lib/db";
import { page, paged, route } from "@/lib/http";
import { getJob, itemJson } from "@/lib/jobs";

/** Per-file results. `?state=failed` filters. */
export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  require_(p, "source:read");
  const { limit, after } = page(req);
  return tx(p.workspaceId, async (db) => {
    await getJob(db, p, id);
    const rows = await all(db, `SELECT * FROM job_items WHERE job_id = $1 AND ($2::text IS NULL OR state = $2)
       AND ($3::timestamptz IS NULL OR (created_at, id) < ($3, $4::uuid)) ORDER BY created_at DESC, id DESC LIMIT $5`,
      [id, req.nextUrl.searchParams.get("state"), after?.[0] ?? null, after?.[1] ?? null, limit + 1]);
    return paged(rows, limit, itemJson);
  });
});
