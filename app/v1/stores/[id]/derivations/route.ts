import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth } from "@/lib/auth";
import { tx } from "@/lib/db";
import { createDerived } from "@/lib/derive";
import { body, route } from "@/lib/http";
import { StoreName } from "@/lib/names";
import { Filter } from "@/lib/search";
import { storeJson } from "@/lib/stores";

/**
 * Derive a store from parents ({id} + `parents`) and a filter.
 *  view     — live: follows parents' current membership, versions, metadata and deletions (views may nest 3 deep).
 *  snapshot — fixed membership pinned to the versions current at creation. Global source deletion still removes it.
 * The derived store reuses the parents' vectors and never widens access.
 */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  const b = await body(req, z.object({ name: StoreName, mode: z.enum(["view", "snapshot"]), parents: z.array(z.string().uuid()).max(20).default([]), filter: Filter.default({}) }).strict());
  return tx(p.workspaceId, async (db) => {
    const s = await createDerived(db, p, [id, ...b.parents], b.name, b.mode, b.filter);
    await audit(db, p, `store.derive_${b.mode}`, s.id, { parents: s.definition.parents });
    return Response.json(await storeJson(db, s), { status: 201 });
  });
});
