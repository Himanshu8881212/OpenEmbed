import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth, require_, storeFilter } from "@/lib/auth";
import { all, one, tx } from "@/lib/db";
import { ApiError, body, invalid, page, paged, route } from "@/lib/http";
import { randomStoreName, StoreName } from "@/lib/names";
import { storeJson, type Store } from "@/lib/stores";
import { requireFeature } from "@/lib/usage";


export const GET = route(async (req) => {
  const p = await auth(req);
  require_(p, "search");
  const { limit, after } = page(req);
  const name = req.nextUrl.searchParams.get("name");
  return tx(p.workspaceId, async (db) => {
    const rows = await all<Store>(db,
      `SELECT s.*, r.profile_id FROM stores s JOIN index_revisions r ON r.id = s.active_revision_id
        WHERE s.deleted_at IS NULL AND ($1::uuid[] IS NULL OR s.id = ANY($1)) AND ($2::text IS NULL OR lower(s.name) = lower($2))
          AND ($3::timestamptz IS NULL OR (s.created_at, s.id) < ($3, $4::uuid))
        ORDER BY s.created_at DESC, s.id DESC LIMIT $5`,
      [storeFilter(p), name, after?.[0] ?? null, after?.[1] ?? null, limit + 1]);
    const out = paged(rows, limit);
    out.data = await Promise.all((out.data as Store[]).map((s) => storeJson(db, s)));
    return out;
  });
});

export const POST = route(async (req) => {
  const p = await auth(req);
  require_(p, "source:write");
  if (p.kind === "key") throw new ApiError(403, "ACCESS_DENIED", "API keys cannot create stores");
  const b = await body(req, z.object({ name: StoreName.optional(), profile_id: z.string().optional() }).strict());
  return tx(p.workspaceId, async (db) => {
    const prof = b.profile_id ? await one(db, "SELECT id, workspace_id FROM embedding_profiles WHERE id = $1", [b.profile_id]) : await one(db, "SELECT id, workspace_id FROM embedding_profiles WHERE id = $1 AND workspace_id IS NULL", [process.env.KB_DEFAULT_PROFILE ?? "eg2-914f7f8-fp32-p4"]);
    if (!prof) throw invalid("Unknown embedding profile", "profile_id");
    if (b.profile_id && prof.workspace_id) await requireFeature(db, "custom_profiles");
    if (!b.name) { // generated readable name, unique in the workspace
      for (let i = 0; i < 10 && !b.name; i++) { const n = randomStoreName(); if (!(await one(db, "SELECT 1 FROM stores WHERE deleted_at IS NULL AND lower(name) = $1", [n]))) b.name = n; }
      if (!b.name) throw new ApiError(409, "CONFLICT", "Could not generate a unique name; supply one");
    }
    if (await one(db, "SELECT 1 FROM stores WHERE deleted_at IS NULL AND lower(name) = lower($1)", [b.name])) throw new ApiError(409, "CONFLICT", "A store with this name already exists");
    const s = await one(db, "INSERT INTO stores (workspace_id, name, created_by) VALUES (kb_ws(), $1, $2) RETURNING id", [b.name, p.actor]);
    const r = await one(db, "INSERT INTO index_revisions (workspace_id, store_id, profile_id, state, promoted_at) VALUES (kb_ws(), $1, $2, 'active', now()) RETURNING id", [s.id, prof.id]);
    await db.query("UPDATE stores SET active_revision_id = $2 WHERE id = $1", [s.id, r.id]);
    await audit(db, p, "store.create", s.id, { name: b.name });
    const full = await one<Store>(db, "SELECT s.*, r.profile_id FROM stores s JOIN index_revisions r ON r.id = s.active_revision_id WHERE s.id = $1", [s.id]);
    return Response.json(await storeJson(db, full!), { status: 201 });
  });
});
