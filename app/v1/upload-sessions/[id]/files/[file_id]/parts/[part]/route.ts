import { createHash } from "node:crypto";
import { UploadPartCommand } from "@aws-sdk/client-s3";
import { auth, require_ } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { ApiError, invalid, notFound, route } from "@/lib/http";
import { bucket, s3 } from "@/lib/s3";
import { getSession } from "@/lib/uploads";

/**
 * Upload one part (raw bytes). Part n (1-based) must be exactly part_bytes long except the last.
 * Optional `x-part-sha256` (hex) is verified. Re-sending a part replaces it (resume-safe).
 */
export const PUT = route(async (req, { id, file_id, part }) => {
  const p = await auth(req);
  require_(p, "source:write");
  const n = Number(part);
  const f = await tx(p.workspaceId, async (db) => {
    const s = await getSession(db, p, id);
    if (s.state !== "open") throw new ApiError(409, "CONFLICT", `Session is ${s.state}`);
    if (new Date(s.expires_at) < new Date()) throw new ApiError(410, "SESSION_EXPIRED", "The upload session expired; create a new session");
    const f = await one(db, "SELECT * FROM upload_files WHERE id = $1 AND session_id = $2", [file_id, id]);
    if (!f) throw notFound("Upload file");
    return f;
  });
  const size = Number(f.size), parts = Math.ceil(size / f.part_size);
  if (!Number.isInteger(n) || n < 1 || n > parts) throw invalid(`Part must be 1..${parts}`, "part");
  const expected = n < parts ? f.part_size : size - f.part_size * (parts - 1);
  const declared = Number(req.headers.get("content-length") ?? expected);
  if (declared > expected) throw new ApiError(413, "INPUT_TOO_LARGE", `Part ${n} must be ${expected} bytes`);
  const buf = Buffer.from(await req.arrayBuffer());
  if (buf.length !== expected) throw invalid(`Part ${n} must be ${expected} bytes, received ${buf.length}`, "part");
  const want = req.headers.get("x-part-sha256");
  if (want && createHash("sha256").update(buf).digest("hex") !== want.toLowerCase()) throw new ApiError(400, "CHECKSUM_MISMATCH", `Part ${n} does not match x-part-sha256`);
  const r = await s3.send(new UploadPartCommand({ Bucket: bucket(), Key: f.object_key, UploadId: f.s3_upload_id, PartNumber: n, Body: buf }));
  await tx(p.workspaceId, (db) => db.query(
    `INSERT INTO upload_parts (workspace_id, upload_file_id, part_no, size, etag) VALUES (kb_ws(), $1, $2, $3, $4)
     ON CONFLICT (upload_file_id, part_no) DO UPDATE SET size = excluded.size, etag = excluded.etag`, [file_id, n, buf.length, r.ETag]));
  return { file_id, part: n, size: buf.length, received: true };
});
