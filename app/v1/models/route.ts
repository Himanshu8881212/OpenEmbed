import { auth } from "@/lib/auth";
import { all, tx } from "@/lib/db";
import { route } from "@/lib/http";

/** OpenAI-style model list: immutable, purpose-specific embedding aliases only. */
export const GET = route(async (req) => {
  const p = await auth(req);
  return tx(p.workspaceId, async (db) => ({
    object: "list",
    data: (await all(db, "SELECT a.*, extract(epoch FROM a.created_at)::bigint created FROM model_aliases a ORDER BY a.alias")).map((a) => ({
      id: a.alias, object: "model", created: Number(a.created), owned_by: "knowledge-store", purpose: a.purpose, profile_id: a.profile_id,
    })),
  }));
}, { openai: true });
