// Applies db/migrations/*.sql in order (once each) as the owner role, then ensures the S3 bucket exists.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import pg from "pg";
import { S3Client, CreateBucketCommand, HeadBucketCommand } from "@aws-sdk/client-s3";
if (existsSync(".env")) process.loadEnvFile(".env"); // optional: containers use real environment variables
const db = new pg.Client({ connectionString: process.env.KB_MIGRATE_DATABASE_URL });
await db.connect();
await db.query("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz DEFAULT now())");
const done = new Set((await db.query("SELECT name FROM schema_migrations")).rows.map((r) => r.name));
for (const f of readdirSync("db/migrations").filter((f) => f.endsWith(".sql")).sort()) {
  if (done.has(f)) continue;
  await db.query("BEGIN");
  try {
    await db.query(readFileSync(`db/migrations/${f}`, "utf8"));
    await db.query("INSERT INTO schema_migrations (name) VALUES ($1)", [f]);
    await db.query("COMMIT");
    console.log("applied", f);
  } catch (e) { await db.query("ROLLBACK"); console.error("failed", f); throw e; }
}
await db.end();
const s3 = new S3Client({ endpoint: process.env.KB_S3_ENDPOINT, region: process.env.KB_S3_REGION, forcePathStyle: true,
  credentials: { accessKeyId: process.env.KB_S3_ACCESS_KEY, secretAccessKey: process.env.KB_S3_SECRET_KEY } });
const Bucket = process.env.KB_S3_BUCKET;
for (let attempt = 1; ; attempt++) { // storage may still be starting
  try {
    try { await s3.send(new HeadBucketCommand({ Bucket })); } catch (e) { if (e?.$metadata?.httpStatusCode !== 404 && e?.name !== "NotFound") throw e; await s3.send(new CreateBucketCommand({ Bucket })); console.log("created bucket", Bucket); }
    break;
  } catch (e) { if (attempt >= 30) throw e; await new Promise((r) => setTimeout(r, 2000)); }
}
