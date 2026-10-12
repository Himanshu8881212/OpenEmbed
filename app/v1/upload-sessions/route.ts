import { CreateMultipartUploadCommand } from "@aws-sdk/client-s3";
import { z } from "zod";
import { auth, require_ } from "@/lib/auth";
import { config } from "@/lib/config";
import { one, tx } from "@/lib/db";
import { mediaTypeFor } from "@/lib/formats";
import { ApiError, body, invalid, route } from "@/lib/http";
import { bucket, s3 } from "@/lib/s3";
import { getFile, getStore } from "@/lib/stores";
import { PART_BYTES, SafePath, sessionJson } from "@/lib/uploads";
import { enforce } from "@/lib/usage";

const Req = z.object({
  store_id: z.string().uuid().optional(),
  files: z.array(z.object({
    path: SafePath,
    size: z.number().int().positive(),
    sha256: z.string().regex(/^[0-9a-f]{64}$/, "lowercase hex SHA-256"),
    replaces_file_id: z.string().uuid().optional(),
  }).strict()).min(1),
}).strict();

/** Create a resumable upload session from a manifest. The client sends file bytes; the API never reads client paths. */
export const POST = route(async (req) => {
  const p = await auth(req);
  const b = await body(req, Req);
  const c = config();
  if (b.files.length > c.KB_UPLOAD_MAX_FILES) throw new ApiError(413, "INPUT_TOO_LARGE", `At most ${c.KB_UPLOAD_MAX_FILES} files per session`);
  const seen = new Set<string>();
  for (const [i, f] of b.files.entries()) {
    if (seen.has(f.path)) throw invalid(`Duplicate path ${JSON.stringify(f.path)}`, `files.${i}.path`);
    seen.add(f.path);
    if (f.size > c.KB_UPLOAD_MAX_FILE_BYTES) throw new ApiError(413, "INPUT_TOO_LARGE", `${f.path} exceeds the ${c.KB_UPLOAD_MAX_FILE_BYTES}-byte file limit`, `files.${i}.size`);
    if (!mediaTypeFor(f.path)) throw new ApiError(415, "FORMAT_UNSUPPORTED", `${f.path} is not a supported format; see GET /v1/embedding-profiles`, `files.${i}.path`);
  }
  return tx(p.workspaceId, async (db) => {
    if (b.store_id) await getStore(db, p, b.store_id, "source:write");
    else { require_(p, "source:write"); if (p.kind === "key" && p.storeIds) throw invalid("Store-restricted keys must set store_id", "store_id"); }
    for (const f of b.files) if (f.replaces_file_id) await getFile(db, p, f.replaces_file_id, "source:write");
    await enforce(db, "storage", b.files.reduce((a, f) => a + f.size, 0));
    const s = await one(db, "INSERT INTO upload_sessions (workspace_id, store_id, created_by, expires_at) VALUES (kb_ws(), $1, $2, now() + make_interval(secs => $3)) RETURNING *",
      [b.store_id ?? null, p.actor, c.KB_UPLOAD_SESSION_TTL_SECONDS]);
    for (const f of b.files) {
      const id = crypto.randomUUID();
      const key = `ws/${p.workspaceId}/uploads/${s.id}/${id}`;
      const mp = await s3.send(new CreateMultipartUploadCommand({ Bucket: bucket(), Key: key }));
      await db.query(`INSERT INTO upload_files (id, workspace_id, session_id, path, size, sha256, media_type, replaces_file_id, part_size, s3_upload_id, object_key)
        VALUES ($1, kb_ws(), $2, $3, $4, $5, $6, $7, $8, $9, $10)`, [id, s.id, f.path, f.size, f.sha256, mediaTypeFor(f.path), f.replaces_file_id ?? null, PART_BYTES, mp.UploadId, key]);
    }
    return Response.json(await sessionJson(db, s), { status: 201 });
  });
});
