import { all, one, type Db } from "./db";
import { iso } from "./http";

export async function fileJson(db: Db, f: any) {
  const v = f.current_version_id ? await one(db, "SELECT * FROM file_versions WHERE id = $1", [f.current_version_id]) : null;
  const segs = v ? await one(db, "SELECT count(*)::int n, array_agg(DISTINCT profile_id) profiles FROM segments WHERE file_version_id = $1", [v.id]) : { n: 0, profiles: [] };
  const pending = await one(db, "SELECT count(*)::int n FROM job_items WHERE file_id = $1 AND state IN ('queued','running')", [f.id]);
  const lastFail = await one(db, "SELECT error_code, error_message FROM job_items WHERE file_id = $1 AND state = 'failed' ORDER BY updated_at DESC LIMIT 1", [f.id]);
  const stores = await all(db, "SELECT sf.store_id, s.name, s.kind, sf.pinned_version_id FROM store_files sf JOIN stores s ON s.id = sf.store_id AND s.deleted_at IS NULL WHERE sf.file_id = $1", [f.id]);
  return {
    id: f.id, object: "file", path: f.path, metadata: f.metadata,
    status: pending.n ? "processing" : v ? "published" : lastFail ? "failed" : "pending",
    current_version: v && { id: v.id, version_no: v.version_no, sha256: v.sha256, size: Number(v.size), filename: v.filename, media_type: v.media_type, created_at: iso(v.created_at) },
    segment_count: segs.n, profiles: segs.profiles?.filter(Boolean) ?? [],
    last_error: lastFail ? { code: lastFail.error_code, message: lastFail.error_message } : null,
    stores: stores.map((s) => ({ store_id: s.store_id, name: s.name, kind: s.kind, pinned_version_id: s.pinned_version_id })),
    created_at: iso(f.created_at), updated_at: iso(f.updated_at),
  };
}
