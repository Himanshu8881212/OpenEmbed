import { auth } from "@/lib/auth";
import { all, one, tx } from "@/lib/db";
import { iso, route } from "@/lib/http";
import { getStore } from "@/lib/stores";

export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, id, "search");
    const r = await one(db, `
      SELECT count(*)::int files, coalesce(sum(fv.size),0)::bigint source_bytes,
             (SELECT count(*) FROM segments sg JOIN kb_store_members($1) mm ON sg.file_version_id = mm.version_id WHERE sg.profile_id = $2)::int segments
        FROM kb_store_members($1) m JOIN file_versions fv ON fv.id = m.version_id`, [id, s.profile_id]);
    const by = await all(db, `SELECT sg.modality, count(*)::int n FROM segments sg JOIN kb_store_members($1) m ON sg.file_version_id = m.version_id WHERE sg.profile_id = $2 GROUP BY 1`, [id, s.profile_id]);
    const jobs = await all(db, "SELECT state, count(*)::int n FROM jobs WHERE store_id = $1 GROUP BY 1", [id]);
    const revisions = await all(db, "SELECT id, profile_id, state, created_at, promoted_at FROM index_revisions WHERE store_id = $1 ORDER BY created_at", [id]);
    return { store_id: id, index_revision: s.active_revision_id, profile_id: s.profile_id, files: r.files, source_bytes: Number(r.source_bytes), segments: r.segments,
      segments_by_modality: Object.fromEntries(by.map((x) => [x.modality, x.n])), jobs_by_state: Object.fromEntries(jobs.map((x) => [x.state, x.n])),
      index_revisions: revisions.map((r) => ({ id: r.id, profile_id: r.profile_id, state: r.state, created_at: iso(r.created_at), promoted_at: iso(r.promoted_at) })) };
  });
});
