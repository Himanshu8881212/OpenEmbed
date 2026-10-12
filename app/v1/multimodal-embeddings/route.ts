import { z } from "zod";
import { assetPart } from "@/lib/assets";
import { auth, require_ } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { ApiError, body, route } from "@/lib/http";
import { documentText, embed, queryText, type Part, type Profile } from "@/lib/inference";
import { enforce, record } from "@/lib/usage";

const Req = z.object({
  profile_id: z.string(),
  purpose: z.enum(["query", "document"]),
  encoding_format: z.enum(["float", "base64"]).default("float"),
  inputs: z.array(z.object({
    parts: z.array(z.discriminatedUnion("type", [
      z.object({ type: z.literal("text"), text: z.string().min(1).max(20000) }).strict(),
      z.object({ type: z.enum(["image", "audio", "video"]), asset_id: z.string().uuid() }).strict(),
    ])).min(1).max(16),
  }).strict()).min(1).max(16),
}).strict();

/** Platform extension (not OpenAI): ordered text/media parts → one vector per input. Media must be uploaded query assets. */
export const POST = route(async (req, _p, requestId) => {
  const p = await auth(req);
  require_(p, "embeddings");
  const b = await body(req, Req);
  return tx(p.workspaceId, async (db) => {
    const prof = await one<Profile>(db, "SELECT * FROM embedding_profiles WHERE id = $1", [b.profile_id]);
    if (!prof) throw new ApiError(404, "RESOURCE_NOT_FOUND", "Unknown profile", "profile_id");
    await enforce(db, "query");
    const inputs: Part[][] = [];
    for (const inp of b.inputs) {
      const parts: Part[] = [];
      for (const part of inp.parts) {
        if (part.type === "text") parts.push({ type: "text", text: b.purpose === "query" ? queryText(prof, part.text) : documentText(prof, part.text) });
        else {
          const a = await assetPart(db, part.asset_id);
          if (a.type !== part.type) throw new ApiError(400, "INVALID_REQUEST", `Asset ${part.asset_id} is ${a.type}, not ${part.type}`, "inputs");
          parts.push(a);
        }
      }
      inputs.push(parts);
    }
    const out = await embed(prof, inputs);
    const tokens = out.reduce((a, r) => a + r.tokens, 0);
    await record(db, "query_media_tokens", tokens, `mm:${requestId}`);
    return {
      object: "list", profile_id: prof.id, purpose: b.purpose,
      data: out.map((r, index) => ({ object: "embedding", index, embedding: b.encoding_format === "float" ? r.embedding : Buffer.from(new Float32Array(r.embedding).buffer).toString("base64"), tokens: r.tokens })),
      usage: { tokens, unit: "model_tokens" },
    };
  });
});
