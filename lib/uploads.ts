import { AbortMultipartUploadCommand } from "@aws-sdk/client-s3";
import { z } from "zod";
import type { Principal } from "./auth";
import { all, one, type Db } from "./db";
import { iso, notFound } from "./http";
import { bucket, s3 } from "./s3";

export const PART_BYTES = 8 * 1024 * 1024;

/** Relative POSIX path from the client's folder. Rejects absolute paths, traversal, backslashes, control characters. */
export const SafePath = z.string().min(1).max(1024).transform((s) => s.normalize("NFC")).refine((s) =>
  !s.startsWith("/") && !s.includes("\\") && !/[\x00-\x1f\x7f]/.test(s) && !/^[A-Za-z]:/.test(s) &&
  s.split("/").every((seg) => seg !== "" && seg !== "." && seg !== ".."), "must be a relative path inside the uploaded folder (no '..', absolute or drive paths)");

export async function getSession(db: Db, p: Principal, id: string) {
  const s = await one(db, "SELECT * FROM upload_sessions WHERE id = $1", [id]);
  if (!s) throw notFound("Upload session");
  if (p.kind === "key" && p.storeIds && !(s.store_id && p.storeIds.includes(s.store_id))) throw notFound("Upload session");
  return s;
}

export async function sessionJson(db: Db, s: any) {
  const files = await all(db, `SELECT f.*, coalesce(array_agg(p.part_no ORDER BY p.part_no) FILTER (WHERE p.part_no IS NOT NULL), '{}') parts_received
    FROM upload_files f LEFT JOIN upload_parts p ON p.upload_file_id = f.id WHERE f.session_id = $1 GROUP BY f.id ORDER BY f.path`, [s.id]);
  return {
    id: s.id, object: "upload_session", state: s.state, store_id: s.store_id, expires_at: iso(s.expires_at), created_at: iso(s.created_at), job_id: s.job_id,
    part_bytes: PART_BYTES,
    files: files.map((f) => {
      const parts = Math.max(1, Math.ceil(Number(f.size) / f.part_size));
      return { id: f.id, path: f.path, size: Number(f.size), sha256: f.sha256, media_type: f.media_type, parts, parts_received: f.parts_received,
        complete: f.parts_received.length === parts, part_url_template: `/v1/upload-sessions/${s.id}/files/${f.id}/parts/{part}` };
    }),
  };
}

export async function abortMultipart(db: Db, sessionId: string) {
  for (const f of await all(db, "SELECT object_key, s3_upload_id FROM upload_files WHERE session_id = $1 AND s3_upload_id IS NOT NULL", [sessionId]))
    await s3.send(new AbortMultipartUploadCommand({ Bucket: bucket(), Key: f.object_key, UploadId: f.s3_upload_id })).catch(() => {});
}
