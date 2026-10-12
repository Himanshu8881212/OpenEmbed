import { auth } from "@/lib/auth";
import { tx } from "@/lib/db";
import { body, route } from "@/lib/http";
import type { Part } from "@/lib/inference";
import { assetPart } from "@/lib/assets";
import { MODALITIES, queryVector, resultJson, SearchReq, searchBalanced, searchHybrid, searchSegments } from "@/lib/search";
import { getProfile, getStore } from "@/lib/stores";

/** Embed the query with the store's active query profile and return ranked, source-linked evidence. */
export const POST = route(async (req, { id }, requestId) => {
  const p = await auth(req);
  const b = await body(req, SearchReq);
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, id, "search");
    const profile = await getProfile(db, s.profile_id);
    const parts: Part[] = [];
    if (b.query.text) parts.push({ type: "text", text: b.query.text });
    if (b.query.asset_id) parts.push(await assetPart(db, b.query.asset_id));
    const q = await queryVector(db, profile, parts, requestId);
    const exact = req.nextUrl.searchParams.get("exact") === "true";
    // hybrid needs query text; media-only queries are vector searches
    const hybridText = b.mode === "hybrid" && b.query.text ? b.query.text : null;
    const rows = b.balance
      ? await searchBalanced(db, s.id, s.profile_id, q.embedding, b.limit, b.filter ?? {}, exact, b.modalities ?? MODALITIES, hybridText)
      : hybridText
        ? await searchHybrid(db, s.id, s.profile_id, q.embedding, hybridText, b.limit, b.filter, exact, b.modalities ?? null)
        : await searchSegments(db, s.id, s.profile_id, q.embedding, b.limit, b.filter, exact, b.modalities ?? null);
    return { object: "search_result", ranking: b.balance ? "balanced" : "score", mode: hybridText ? "hybrid" : "vector", request_id: requestId, store_id: s.id, index_revision: s.active_revision_id, profile_id: s.profile_id,
      results: rows.map((r) => ({ request_id: requestId, store_id: s.id, index_revision: s.active_revision_id, profile_id: s.profile_id, ...resultJson(r) })),
      usage: { query_tokens: q.tokens } };
  });
});
