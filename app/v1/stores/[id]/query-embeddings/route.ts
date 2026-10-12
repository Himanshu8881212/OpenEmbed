import { z } from "zod";
import { assetPart } from "@/lib/assets";
import { auth } from "@/lib/auth";
import { tx } from "@/lib/db";
import { body, route } from "@/lib/http";
import type { Part } from "@/lib/inference";
import { queryVector } from "@/lib/search";
import { getProfile, getStore, queryAlias } from "@/lib/stores";

/** Advanced: the query vector for this store's active profile (same preparation as store search). */
export const POST = route(async (req, { id }, requestId) => {
  const p = await auth(req);
  const b = await body(req, z.object({ query: z.object({ text: z.string().min(1).max(20000).optional(), asset_id: z.string().uuid().optional() }).strict().refine((q) => q.text || q.asset_id, "query.text or query.asset_id is required") }).strict());
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, id, "search");
    const profile = await getProfile(db, s.profile_id);
    const parts: Part[] = [];
    if (b.query.text) parts.push({ type: "text", text: b.query.text });
    if (b.query.asset_id) parts.push(await assetPart(db, b.query.asset_id));
    const q = await queryVector(db, profile, parts, requestId);
    return { object: "query_embedding", store_id: s.id, profile_id: s.profile_id, model: await queryAlias(db, s.profile_id), index_revision: s.active_revision_id,
      dimensions: q.embedding.length, embedding: q.embedding, usage: { tokens: q.tokens } };
  });
});
