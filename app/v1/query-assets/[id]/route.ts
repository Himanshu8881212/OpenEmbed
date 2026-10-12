import { DeleteObjectCommand } from "@aws-sdk/client-s3";
import { auth, require_ } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { notFound, route } from "@/lib/http";
import { bucket, s3 } from "@/lib/s3";

export const DELETE = route(async (req, { id }) => {
  const p = await auth(req);
  require_(p, "embeddings");
  return tx(p.workspaceId, async (db) => {
    const a = await one(db, "DELETE FROM query_assets WHERE id = $1 RETURNING object_key", [id]);
    if (!a) throw notFound("Query asset");
    await s3.send(new DeleteObjectCommand({ Bucket: bucket(), Key: a.object_key }));
    return new Response(null, { status: 204 });
  });
});
