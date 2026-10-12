import { auth, require_ } from "@/lib/auth";
import { tx } from "@/lib/db";
import { ApiError, route } from "@/lib/http";
import { documentText, embed, queryText, type Profile } from "@/lib/inference";
import { enforce, record } from "@/lib/usage";

const ALLOWED = new Set(["model", "input", "encoding_format", "dimensions", "user"]);
const MAX_INPUTS = 256;

/**
 * OpenAI-compatible text embeddings subset: input string | string[]; encoding_format float | base64;
 * dimensions only equal to the alias dimension; token-ID inputs and unknown parameters are rejected.
 */
export const POST = route(async (req, _p, requestId) => {
  const p = await auth(req);
  require_(p, "embeddings");
  let b: any;
  try { b = await req.json(); } catch { throw new ApiError(400, "INVALID_REQUEST", "Body must be valid JSON"); }
  if (!b || typeof b !== "object" || Array.isArray(b)) throw new ApiError(400, "INVALID_REQUEST", "Body must be a JSON object");
  for (const k of Object.keys(b)) if (!ALLOWED.has(k)) throw new ApiError(400, "UNSUPPORTED_PARAMETER", `Unsupported parameter: ${k}`, k);
  if (typeof b.model !== "string") throw new ApiError(400, "INVALID_REQUEST", "model is required", "model");
  const isTokens = (x: unknown) => typeof x === "number" || (Array.isArray(x) && x.length > 0 && x.every((y) => typeof y === "number"));
  if (isTokens(b.input) || (Array.isArray(b.input) && b.input.some(isTokens)))
    throw new ApiError(400, "UNSUPPORTED_INPUT", "Token-ID inputs are not supported; send text strings (Gemma tokenizer IDs differ from OpenAI's)", "input");
  const inputs: string[] = typeof b.input === "string" ? [b.input] : b.input;
  if (!Array.isArray(inputs) || !inputs.length || !inputs.every((x) => typeof x === "string"))
    throw new ApiError(400, "INVALID_REQUEST", "input must be a string or a non-empty array of strings; media inputs use /v1/multimodal-embeddings", "input");
  if (inputs.length > MAX_INPUTS) throw new ApiError(400, "INVALID_REQUEST", `At most ${MAX_INPUTS} inputs per request`, "input");
  if (inputs.some((x) => x.length === 0)) throw new ApiError(400, "INVALID_REQUEST", "input strings must not be empty", "input");
  const fmt = b.encoding_format ?? "float";
  if (fmt !== "float" && fmt !== "base64") throw new ApiError(400, "INVALID_REQUEST", "encoding_format must be float or base64", "encoding_format");
  if (b.user !== undefined && typeof b.user !== "string") throw new ApiError(400, "INVALID_REQUEST", "user must be a string", "user");
  return tx(p.workspaceId, async (db) => {
    const { rows: [m] } = await db.query("SELECT a.alias, a.purpose, p.* FROM model_aliases a JOIN embedding_profiles p ON p.id = a.profile_id WHERE a.alias = $1", [b.model]);
    if (!m) throw new ApiError(404, "MODEL_NOT_FOUND", `Unknown model alias '${b.model}'. Use an alias from GET /v1/models`, "model");
    if (b.dimensions !== undefined && b.dimensions !== m.dims) throw new ApiError(400, "UNSUPPORTED_DIMENSIONS", `This alias produces ${m.dims} dimensions only`, "dimensions");
    await enforce(db, "query");
    const prof = m as Profile;
    const out = await embed(prof, inputs.map((t) => [{ type: "text", text: m.purpose === "query" ? queryText(prof, t) : documentText(prof, t) }]));
    const tokens = out.reduce((a, r) => a + r.tokens, 0);
    await record(db, "query_text_tokens", tokens, `emb:${requestId}`);
    return {
      object: "list", model: m.alias,
      data: out.map((r, index) => ({ object: "embedding", index, embedding: fmt === "float" ? r.embedding : Buffer.from(new Float32Array(r.embedding).buffer).toString("base64") })),
      usage: { prompt_tokens: tokens, total_tokens: tokens },
    };
  });
}, { openai: true });
