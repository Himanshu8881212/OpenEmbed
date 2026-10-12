import { GetObjectCommand } from "@aws-sdk/client-s3";
import { auth } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { notFound, route } from "@/lib/http";
import { bucket, s3 } from "@/lib/s3";
import { getFile } from "@/lib/stores";

/** Stream the original bytes (current or given version). Access is rechecked on every request; no long-lived URLs are issued. */
export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  const want = req.nextUrl.searchParams.get("version_id");
  const v = await tx(p.workspaceId, async (db) => {
    const f = await getFile(db, p, id, "source:read");
    const vid = want ?? f.current_version_id;
    if (!vid || !/^[0-9a-f-]{36}$/i.test(vid)) throw notFound("Version");
    const v = await one(db, "SELECT v.*, b.object_key FROM file_versions v JOIN blobs b ON b.workspace_id = v.workspace_id AND b.sha256 = v.sha256 WHERE v.id = $1 AND v.file_id = $2", [vid, id]);
    if (!v) throw notFound("Version");
    if (p.kind === "key" && p.storeIds) {
      // store-restricted keys may read only versions their stores expose (e.g. a snapshot's pinned version)
      const ok = await one(db, "SELECT 1 FROM unnest($2::uuid[]) sid WHERE EXISTS (SELECT 1 FROM kb_store_members(sid) m WHERE m.version_id = $1)", [vid, p.storeIds]);
      if (!ok) throw notFound("Version");
    }
    return v;
  });
  const o = await s3.send(new GetObjectCommand({ Bucket: bucket(), Key: v.object_key }));
  return new Response(o.Body!.transformToWebStream(), { headers: {
    "content-type": v.media_type, "content-length": String(v.size),
    "content-disposition": `attachment; filename*=UTF-8''${encodeURIComponent(v.filename)}`, "x-content-type-options": "nosniff", "cache-control": "private, no-store",
  } });
});
