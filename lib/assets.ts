import { GetObjectCommand } from "@aws-sdk/client-s3";
import type { Db } from "./db";
import { ApiError, notFound } from "./http";
import type { Part } from "./inference";
import { bucket, s3 } from "./s3";

/** Resolve a temporary query asset (workspace-scoped by RLS, expiry rechecked) into an inference part. */
export async function assetPart(db: Db, id: string): Promise<Part> {
  const { rows: [a] } = await db.query("SELECT * FROM query_assets WHERE id = $1", [id]);
  if (!a) throw notFound("Query asset");
  if (new Date(a.expires_at) < new Date()) throw new ApiError(410, "ASSET_EXPIRED", "The query asset expired; upload it again");
  const o = await s3.send(new GetObjectCommand({ Bucket: bucket(), Key: a.object_key }));
  const data = Buffer.from(await o.Body!.transformToByteArray()).toString("base64");
  const type = a.media_type.split("/")[0] as "image" | "audio" | "video";
  return { type, data_b64: data };
}
