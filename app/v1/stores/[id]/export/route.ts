import { auth } from "@/lib/auth";
import { all, tx } from "@/lib/db";
import { invalid, route } from "@/lib/http";
import { getStore } from "@/lib/stores";

const BATCH = 500;

/**
 * Export the store's indexed segments as NDJSON: one line per segment with source reference, location, text and the
 * 768-d embedding (active profile). `?include=embedding,content` (default both). Streams in keyset batches; each batch
 * re-applies membership and permissions. Requires `source:read`.
 */
export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  const inc = new Set((req.nextUrl.searchParams.get("include") ?? "embedding,content").split(",").map((x) => x.trim()));
  for (const x of inc) if (!["embedding", "content"].includes(x)) throw invalid("include accepts embedding, content", "include");
  const s = await tx(p.workspaceId, (db) => getStore(db, p, id, "source:read"));
  let last = "00000000-0000-0000-0000-000000000000", done = false;
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    async pull(ctl) {
      if (done) return ctl.close();
      const rows = await tx(p.workspaceId, async (db) => {
        await getStore(db, p, id, "source:read"); // access rechecked per batch (revocation mid-export stops it)
        return all(db, `SELECT sg.id, sg.ordinal, sg.modality, sg.location, sg.token_count, ${inc.has("content") ? "sg.content," : ""} ${inc.has("embedding") ? "sg.embedding::text AS embedding," : ""}
            f.id AS file_id, f.path, f.metadata, fv.id AS version_id, fv.version_no, fv.filename, fv.media_type, fv.sha256
          FROM kb_store_members($1) m JOIN segments sg ON sg.file_version_id = m.version_id AND sg.profile_id = $2
          JOIN files f ON f.id = m.file_id JOIN file_versions fv ON fv.id = m.version_id
          WHERE sg.id > $3 ORDER BY sg.id LIMIT ${BATCH}`, [id, s.profile_id, last]);
      });
      if (rows.length < BATCH) done = true;
      if (!rows.length) return ctl.close();
      last = rows[rows.length - 1].id;
      ctl.enqueue(enc.encode(rows.map((r) => JSON.stringify({
        segment_id: r.id, store_id: s.id, profile_id: s.profile_id, index_revision: s.active_revision_id, modality: r.modality, ordinal: r.ordinal, token_count: r.token_count,
        source: { file_id: r.file_id, version_id: r.version_id, version_no: r.version_no, path: r.path, filename: r.filename, media_type: r.media_type, sha256: r.sha256, metadata: r.metadata, location: r.location },
        ...(inc.has("content") ? { content: r.content } : {}), ...(inc.has("embedding") ? { embedding: JSON.parse(r.embedding) } : {}),
      })).join("\n") + "\n"));
    },
  });
  return new Response(stream, { headers: {
    "content-type": "application/x-ndjson; charset=utf-8", "content-disposition": `attachment; filename="${s.name}.jsonl"`,
    "x-kb-profile": s.profile_id, "x-kb-index-revision": s.active_revision_id, "cache-control": "private, no-store",
  } });
});
