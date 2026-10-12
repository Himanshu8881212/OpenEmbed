import { z } from "zod";

const Plan = z.object({
  name: z.string(),
  allow_excess: z.boolean(),
  limits: z.object({ storage_bytes: z.number().int().positive(), index_tokens_month: z.number().int().positive(), query_tokens_month: z.number().int().positive(), requests_per_minute: z.number().int().positive().optional() }).passthrough(),
  features: z.record(z.string(), z.boolean()).default({}), // provider-controlled, e.g. { custom_profiles: true }
}).passthrough();
export type Plan = z.infer<typeof Plan>;

const Env = z.object({
  KB_DATABASE_URL: z.string().url(),
  KB_S3_ENDPOINT: z.string().url(),
  KB_S3_REGION: z.string().min(1),
  KB_S3_BUCKET: z.string().min(3),
  KB_S3_ACCESS_KEY: z.string().min(1),
  KB_S3_SECRET_KEY: z.string().min(1),
  KB_OIDC_ISSUER: z.string().url(),
  KB_OIDC_CLI_CLIENT_ID: z.string().min(1),
  KB_OIDC_ALLOWED_CLIENTS: z.string().transform((s) => s.split(",").map((x) => x.trim()).filter(Boolean)),
  KB_INFERENCE_URL: z.string().url(),
  KB_INFERENCE_TOKEN: z.string().min(8),
  KB_PUBLIC_BASE_URL: z.string().url().transform((s) => s.replace(/\/$/, "")),
  KB_DEFAULT_PLAN: z.string().transform((s) => Plan.parse(JSON.parse(s))),
  KB_UPLOAD_MAX_FILE_BYTES: z.coerce.number().int().positive().default(512 * 1024 * 1024),
  KB_UPLOAD_MAX_FILES: z.coerce.number().int().positive().default(1000),
  KB_UPLOAD_SESSION_TTL_SECONDS: z.coerce.number().int().positive().default(24 * 3600),
  KB_QUERY_ASSET_TTL_SECONDS: z.coerce.number().int().positive().default(3600),
});

let cached: z.infer<typeof Env> | undefined;
/** Validated configuration; throws listing every invalid variable (fail fast, no partial config). */
export function config() {
  if (!cached) {
    const r = Env.safeParse(process.env);
    if (!r.success) throw new Error("Invalid configuration: " + r.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; "));
    cached = r.data;
  }
  return cached;
}
export { Plan };
