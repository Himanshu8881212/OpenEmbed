import { can, require_, type Perm, type Principal } from "./auth";
import { config } from "./config";
import { all, one, type Db } from "./db";
import { denied, iso, notFound } from "./http";
import type { Profile } from "./inference";

export type Store = {
  id: string; workspace_id: string; name: string; kind: string; definition: any; active_revision_id: string;
  profile_id: string; created_at: Date; updated_at: Date;
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Load a live store visible to the principal and check permission. */
export async function getStore(db: Db, p: Principal, ref: string, perm: Perm): Promise<Store> {
  if (!UUID.test(ref)) throw notFound("Store");
  const s = await one<Store>(db,
    `SELECT s.*, r.profile_id FROM stores s JOIN index_revisions r ON r.id = s.active_revision_id
      WHERE s.deleted_at IS NULL AND s.id = $1::uuid`, [ref]);
  if (!s) throw notFound("Store");
  if (!can(p, perm, s.id)) {
    if (p.kind === "key" && p.storeIds && !p.storeIds.includes(s.id)) throw notFound("Store"); // conceal stores outside the key's scope
    throw denied();
  }
  return s;
}

export async function getProfile(db: Db, id: string): Promise<Profile & { preparation: any; embedded_metadata_fields: string[] }> {
  return (await one(db, "SELECT * FROM embedding_profiles WHERE id = $1", [id]))!;
}

export async function queryAlias(db: Db, profileId: string): Promise<string> {
  return (await one(db, "SELECT alias FROM model_aliases WHERE profile_id = $1 AND purpose = 'query'", [profileId]))!.alias;
}

export async function storeJson(db: Db, s: Store) {
  const stats = await one(db,
    `SELECT count(DISTINCT m.file_id)::int files, count(seg.id)::int segments
       FROM kb_store_members($1) m LEFT JOIN segments seg ON seg.file_version_id = m.version_id AND seg.profile_id = $2`, [s.id, s.profile_id]);
  return {
    id: s.id, object: "store", name: s.name, kind: s.kind, definition: s.definition,
    profile_id: s.profile_id, index_revision: s.active_revision_id, query_model: await queryAlias(db, s.profile_id),
    file_count: stats.files, segment_count: stats.segments, state: stats.segments ? "ready" : "empty",
    created_at: iso(s.created_at), updated_at: iso(s.updated_at),
  };
}

/** Load a file that is visible: in the workspace, not deleted. Keys restricted to stores must reach it through one of them. */
export async function getFile(db: Db, p: Principal, id: string, perm: Perm) {
  const f = await one(db, "SELECT * FROM files WHERE id = $1 AND deleted_at IS NULL", [id]);
  if (!f) throw notFound("File");
  if (p.kind === "key" && p.storeIds) {
    const ok = await all(db, "SELECT 1 FROM unnest($2::uuid[]) sid WHERE EXISTS (SELECT 1 FROM kb_store_members(sid) m WHERE m.file_id = $1)", [id, p.storeIds]);
    if (!ok.length) throw notFound("File");
  }
  require_(p, perm);
  return f;
}

export const baseUrl = () => config().KB_PUBLIC_BASE_URL;
