import { PutObjectCommand } from "@aws-sdk/client-s3";
import { auth, require_ } from "@/lib/auth";
import { config } from "@/lib/config";
import { one, tx } from "@/lib/db";
import { QUERY_ASSET_TYPES } from "@/lib/formats";
import { ApiError, iso, route } from "@/lib/http";
import { bucket, s3 } from "@/lib/s3";

const MAX = 20 * 1024 * 1024;

/** Upload a temporary media query asset (raw body, Content-Type = media type). Expires after KB_QUERY_ASSET_TTL_SECONDS. */
export const POST = route(async (req) => {
  const p = await auth(req);
  require_(p, "embeddings");
  const type = (req.headers.get("content-type") ?? "").split(";")[0].trim().toLowerCase();
  if (!QUERY_ASSET_TYPES.includes(type)) throw new ApiError(415, "FORMAT_UNSUPPORTED", `Content-Type must be one of ${QUERY_ASSET_TYPES.join(", ")}`);
  if (Number(req.headers.get("content-length") ?? 0) > MAX) throw new ApiError(413, "INPUT_TOO_LARGE", `Query assets are limited to ${MAX} bytes`);
  const buf = Buffer.from(await req.arrayBuffer());
  if (!buf.length) throw new ApiError(400, "INVALID_REQUEST", "Empty body");
  if (buf.length > MAX) throw new ApiError(413, "INPUT_TOO_LARGE", `Query assets are limited to ${MAX} bytes`);
  const id = crypto.randomUUID();
  const key = `ws/${p.workspaceId}/query-assets/${id}`;
  await s3.send(new PutObjectCommand({ Bucket: bucket(), Key: key, Body: buf, ContentType: type }));
  return tx(p.workspaceId, async (db) => {
    const a = await one(db, "INSERT INTO query_assets (id, workspace_id, media_type, size, object_key, expires_at) VALUES ($1, kb_ws(), $2, $3, $4, now() + make_interval(secs => $5)) RETURNING *",
      [id, type, buf.length, key, config().KB_QUERY_ASSET_TTL_SECONDS]);
    return Response.json({ id: a.id, object: "query_asset", media_type: a.media_type, size: Number(a.size), expires_at: iso(a.expires_at) }, { status: 201 });
  });
});
