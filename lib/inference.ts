import { config } from "./config";
import { ApiError } from "./http";

export type Part = { type: "text"; text: string } | { type: "image" | "audio" | "video"; data_b64: string };
export type Profile = { id: string; model: string; revision: string; dtype: string; query_prompt: string; document_template: string; dims: number; preparation?: any };

/** Embeds inputs on the hosted model. Prompts are applied by the caller. Returns vectors + measured tokens in input order. */
export async function embed(profile: Profile, inputs: Part[][]): Promise<{ embedding: number[]; tokens: number }[]> {
  const c = config();
  let res: Response;
  try {
    res = await fetch(`${c.KB_INFERENCE_URL}/embed`, {
      method: "POST",
      headers: { authorization: `Bearer ${c.KB_INFERENCE_TOKEN}`, "content-type": "application/json" },
      body: JSON.stringify({ profile: { model: profile.model, revision: profile.revision, dtype: profile.dtype }, inputs: inputs.map((parts) => ({ parts })),
        // media queries use the same processor settings as the index (e.g. video frame detail)
        processing: Object.fromEntries(["image", "video"].filter((k) => profile.preparation?.[k]?.max_soft_tokens).map((k) => [k, { max_soft_tokens: profile.preparation[k].max_soft_tokens }])) }),
      signal: AbortSignal.timeout(120_000),
    });
  } catch {
    throw new ApiError(503, "SERVICE_UNAVAILABLE", "The embedding service is unavailable");
  }
  const j: any = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = j.detail ?? {};
    if (res.status === 413) throw new ApiError(413, "INPUT_TOO_LARGE", d.message ?? "Input exceeds the model budget", d.index != null ? `input.${d.index}` : undefined);
    if (res.status === 415) throw new ApiError(415, "FORMAT_UNSUPPORTED", d.message ?? "Unsupported input");
    if (res.status === 400) throw new ApiError(400, "INVALID_REQUEST", d.message ?? "Invalid input");
    if (res.status === 409) throw new ApiError(503, "SERVICE_UNAVAILABLE", "No inference host serves this profile");
    throw new ApiError(503, "SERVICE_UNAVAILABLE", "The embedding service failed");
  }
  for (const d of j.data) if (d.embedding.length !== profile.dims || !d.embedding.every(Number.isFinite)) throw new ApiError(503, "SERVICE_UNAVAILABLE", "Invalid vector from embedding service");
  return j.data;
}

export const queryText = (p: Profile, text: string) => p.query_prompt + text;
export const documentText = (p: Profile, text: string, title = "none") => p.document_template.replace("{title}", title).replace("{content}", text);
export const toVector = (v: number[]) => `[${v.join(",")}]`;
