import { HeadBucketCommand } from "@aws-sdk/client-s3";
import { config } from "@/lib/config";
import { pool } from "@/lib/db";
import { bucket, s3 } from "@/lib/s3";

export const dynamic = "force-dynamic";
/** Readiness: configuration, database (+ migrations), object storage, inference host. */
export async function GET() {
  const checks: Record<string, string> = {};
  const run = async (name: string, f: () => Promise<unknown>) => {
    try { await f(); checks[name] = "ok"; } catch (e) { checks[name] = String((e as Error).message ?? e).slice(0, 200); }
  };
  await run("config", async () => config());
  await run("database", () => pool.query("SELECT 1 FROM embedding_profiles LIMIT 1"));
  await run("object_storage", () => s3.send(new HeadBucketCommand({ Bucket: bucket() })));
  await run("inference", async () => {
    const r = await fetch(`${config().KB_INFERENCE_URL}/readyz`, { signal: AbortSignal.timeout(5000) });
    if (!r.ok) throw new Error(`inference ${r.status}`);
  });
  const ok = Object.values(checks).every((v) => v === "ok");
  return Response.json({ ok, checks }, { status: ok ? 200 : 503 });
}
