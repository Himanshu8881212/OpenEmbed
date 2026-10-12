import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth } from "@/lib/auth";
import { all, tx } from "@/lib/db";
import { createDerived } from "@/lib/derive";
import { body, invalid, route } from "@/lib/http";
import { getStore, storeJson } from "@/lib/stores";

const MAX_SPLITS = 50;
const slug = (v: string) => v.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "empty";

/**
 * Split a store by a metadata field: one live view (or snapshot) per distinct value, named `<prefix>-<value>`.
 * All created in one transaction; existing names are reported as skipped, never overwritten.
 */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  const b = await body(req, z.object({ field: z.string().min(1).max(100), mode: z.enum(["view", "snapshot"]).default("view"), prefix: z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._-]{0,38}$/).optional() }).strict());
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, id, "source:write");
    const values = (await all(db, `SELECT DISTINCT f.metadata->>$2 AS v FROM kb_store_members($1) m JOIN files f ON f.id = m.file_id
      WHERE f.metadata ? $2 AND jsonb_typeof(f.metadata->$2) IN ('string','number','boolean') ORDER BY 1 LIMIT ${MAX_SPLITS + 1}`, [id, b.field])).map((r) => r.v as string);
    if (!values.length) throw invalid(`No source in this store has metadata '${b.field}'`, "field");
    if (values.length > MAX_SPLITS) throw invalid(`'${b.field}' has more than ${MAX_SPLITS} distinct values; filter first`, "field");
    const prefix = b.prefix ?? s.name.slice(0, 38);
    const created = [], skipped = [];
    for (const v of values) {
      const name = `${prefix}-${slug(v)}`.slice(0, 100);
      if ((await all(db, "SELECT 1 FROM stores WHERE deleted_at IS NULL AND lower(name) = lower($1)", [name])).length) { skipped.push({ value: v, name, reason: "name exists" }); continue; }
      // the stored metadata keeps its JSON type; match on the original typed value
      const typed = (await all(db, "SELECT f.metadata->$2 AS t FROM kb_store_members($1) m JOIN files f ON f.id = m.file_id WHERE f.metadata->>$2 = $3 LIMIT 1", [id, b.field, v]))[0].t;
      const d = await createDerived(db, p, [id], name, b.mode, { metadata: { [b.field]: typed } });
      created.push({ value: v, store: await storeJson(db, d) });
    }
    await audit(db, p, "store.split", id, { field: b.field, mode: b.mode, created: created.length });
    return Response.json({ field: b.field, mode: b.mode, created, skipped }, { status: 201 });
  });
});
