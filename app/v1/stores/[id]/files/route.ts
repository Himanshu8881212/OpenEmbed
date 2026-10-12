import { auth } from "@/lib/auth";
import { all, tx } from "@/lib/db";
import { iso, page, paged, route } from "@/lib/http";
import { getStore } from "@/lib/stores";

/** Sources in the store's resolved membership (views/snapshots included), newest first. */
export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  const { limit, after } = page(req);
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, id, "source:read");
    const rows = await all(db, `SELECT f.id, f.path, f.metadata, f.created_at, fv.id version_id, fv.version_no, fv.filename, fv.media_type, fv.size,
        (SELECT count(*) FROM segments sg WHERE sg.file_version_id = fv.id AND sg.profile_id = $2)::int segment_count
      FROM kb_store_members($1) m JOIN files f ON f.id = m.file_id JOIN file_versions fv ON fv.id = m.version_id
      WHERE ($3::timestamptz IS NULL OR (f.created_at, f.id) < ($3, $4::uuid)) ORDER BY f.created_at DESC, f.id DESC LIMIT $5`,
      [s.id, s.profile_id, after?.[0] ?? null, after?.[1] ?? null, limit + 1]);
    return paged(rows, limit, (r: any) => ({ id: r.id, path: r.path, metadata: r.metadata, version: { id: r.version_id, version_no: r.version_no, filename: r.filename, media_type: r.media_type, size: Number(r.size) }, segment_count: r.segment_count, indexed: r.segment_count > 0, created_at: iso(r.created_at) }));
  });
});
