import { randomBytes } from "node:crypto";
import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth, require_ } from "@/lib/auth";
import { config } from "@/lib/config";
import { all, one, tx } from "@/lib/db";
import { FORMATS } from "@/lib/formats";
import { requireFeature } from "@/lib/usage";
import { ApiError, body, invalid, iso, route } from "@/lib/http";

export const GET = route(async (req) => {
  const p = await auth(req);
  const c = config();
  return tx(p.workspaceId, async (db) => ({
    data: (await all(db, "SELECT p.*, (SELECT jsonb_object_agg(purpose, alias) FROM model_aliases a WHERE a.profile_id = p.id) aliases FROM embedding_profiles p ORDER BY created_at")).map((r) => ({
      id: r.id, name: r.name, scope: r.workspace_id ? "workspace" : "global", model: r.model, revision: r.revision, dimensions: r.dims, normalized: r.normalize, dtype: r.dtype,
      query_prompt: r.query_prompt, document_template: r.document_template, preparation: r.preparation,
      embedded_metadata_fields: r.embedded_metadata_fields, adapter_version: r.adapter_version, aliases: r.aliases,
      max_input_tokens: r.preparation.max_tokens, created_at: iso(r.created_at), immutable: true,
    })),
    formats: Object.entries(FORMATS).map(([ext, f]) => ({ extension: ext, ...f })),
    limits: { max_file_bytes: c.KB_UPLOAD_MAX_FILE_BYTES, max_files_per_session: c.KB_UPLOAD_MAX_FILES, part_bytes: 8 * 1024 * 1024, upload_session_ttl_seconds: c.KB_UPLOAD_SESSION_TTL_SECONDS },
  }));
});

const Req = z.object({
  name: z.string().trim().min(1).max(80),
  base_profile_id: z.string().optional(),
  text: z.object({ max_chars: z.number().int().min(200).max(6000), overlap_chars: z.number().int().min(0).max(2000) }).strict(),
  audio: z.object({ segment_seconds: z.number().int().min(5).max(300) }).strict().optional(),
  video: z.object({ segment_seconds: z.number().int().min(5).max(32) }).strict().optional(),
}).strict();

/**
 * Create a workspace-scoped, immutable profile with custom segmentation. Same pinned model, revision, precision and
 * instructions as the base profile (so the hosted model can serve it); only preparation differs. Use it for new
 * stores or via reindex + promotion. Bounds keep every segment inside the model's 8,192-token budget
 * (≤6,000 chars of text; audio ≤300 s at 25 tok/s; video ≤32 frames at 1 fps).
 */
export const POST = route(async (req) => {
  const p = await auth(req);
  if (p.kind === "key") throw new ApiError(403, "ACCESS_DENIED", "API keys cannot create profiles");
  require_(p, "source:write");
  const b = await body(req, Req);
  await tx(p.workspaceId, (db) => requireFeature(db, "custom_profiles"));
  if (b.text.overlap_chars >= b.text.max_chars / 2) throw invalid("overlap_chars must be less than half of max_chars", "text.overlap_chars");
  return tx(p.workspaceId, async (db) => {
    const base = await one(db, "SELECT * FROM embedding_profiles WHERE id = $1", [b.base_profile_id ?? "eg2-914f7f8-fp32-p1"]);
    if (!base) throw invalid("Unknown base profile", "base_profile_id");
    const prep = { ...base.preparation, text: b.text, ...(b.audio ? { audio: { ...base.preparation.audio, ...b.audio } } : {}), ...(b.video ? { video: { ...base.preparation.video, ...b.video } } : {}) };
    const id = `ws-${randomBytes(5).toString("hex")}`;
    await db.query(`INSERT INTO embedding_profiles (id, workspace_id, name, model, revision, dims, normalize, dtype, query_prompt, document_template, preparation, embedded_metadata_fields, adapter_version)
      VALUES ($1, kb_ws(), $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)`,
      [id, b.name, base.model, base.revision, base.dims, base.normalize, base.dtype, base.query_prompt, base.document_template, prep, base.embedded_metadata_fields, base.adapter_version]);
    await db.query("INSERT INTO model_aliases (alias, profile_id, purpose, workspace_id) VALUES ($1, $2, 'query', kb_ws()), ($3, $2, 'document', kb_ws())", [`${id}-query`, id, `${id}-document`]);
    await audit(db, p, "profile.create", id, { name: b.name, text: b.text });
    return Response.json({ id, name: b.name, scope: "workspace", preparation: prep, aliases: { query: `${id}-query`, document: `${id}-document` }, immutable: true }, { status: 201 });
  });
});
