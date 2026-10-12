import { auth } from "@/lib/auth";
import { all, tx } from "@/lib/db";
import { invalid, route } from "@/lib/http";
import { getFile } from "@/lib/stores";

/** Prepared segments of the current (or a given) version: modality, location, text content. Vectors are not returned. */
export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  const u = req.nextUrl.searchParams;
  const limit = Math.min(Math.max(Number(u.get("limit") ?? 100) || 100, 1), 500);
  const from = Math.max(Number(u.get("cursor") ?? 0) || 0, 0);
  return tx(p.workspaceId, async (db) => {
    const f = await getFile(db, p, id, "source:read");
    const version = u.get("version_id") ?? f.current_version_id;
    if (!version) return { data: [], next_cursor: null };
    if (!/^[0-9a-f-]{36}$/i.test(version)) throw invalid("Invalid version_id", "version_id");
    const rows = await all(db, `SELECT s.id, s.profile_id, s.ordinal, s.modality, s.location, s.content, s.token_count FROM segments s
      JOIN file_versions v ON v.id = s.file_version_id AND v.file_id = $1 WHERE s.file_version_id = $2 AND s.ordinal >= $3
      ORDER BY s.profile_id, s.ordinal LIMIT $4`, [id, version, from, limit + 1]);
    const more = rows.length > limit;
    return { version_id: version, data: rows.slice(0, limit), next_cursor: more ? String(rows[limit].ordinal) : null };
  });
});
