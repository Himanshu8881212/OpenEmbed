// After a restore: replay ledger entries newer than the backup so deleted material and revoked access stay gone.
// Usage: node scripts/reapply-deletions.mjs BACKUP_TIMESTAMP_ISO
import { existsSync } from "node:fs";
import { GetObjectCommand, ListObjectsV2Command, S3Client } from "@aws-sdk/client-s3";
import pg from "pg";
if (existsSync(".env")) process.loadEnvFile(".env"); // optional: containers use real environment variables
const since = process.argv[2];
if (!since || Number.isNaN(Date.parse(since))) { console.error("usage: reapply-deletions.mjs BACKUP_TIMESTAMP_ISO"); process.exit(1); }
const s3 = new S3Client({ endpoint: process.env.KB_S3_ENDPOINT, region: process.env.KB_S3_REGION, forcePathStyle: true, credentials: { accessKeyId: process.env.KB_S3_ACCESS_KEY, secretAccessKey: process.env.KB_S3_SECRET_KEY } });
const Bucket = process.env.KB_S3_BUCKET;
const db = new pg.Client({ connectionString: process.env.KB_MIGRATE_DATABASE_URL });
await db.connect();
const SQL = {
  "file.delete": ["UPDATE files SET deleted_at = coalesce(deleted_at, $2) WHERE id = $1"],
  "store.delete": ["UPDATE stores SET deleted_at = coalesce(deleted_at, $2) WHERE id = $1", "DELETE FROM store_files WHERE store_id = $1"],
  "api_key.revoke": ["UPDATE api_keys SET revoked_at = coalesce(revoked_at, $2) WHERE id = $1"],
  "member.remove": ["DELETE FROM members WHERE id = $1"],
};
let n = 0;
for (let token; ; ) {
  const r = await s3.send(new ListObjectsV2Command({ Bucket, Prefix: "ledger/", StartAfter: `ledger/${new Date(since).toISOString()}`, ContinuationToken: token }));
  for (const o of r.Contents ?? []) {
    const e = JSON.parse(await (await s3.send(new GetObjectCommand({ Bucket, Key: o.Key }))).Body.transformToString());
    for (const q of SQL[e.kind] ?? []) await db.query(q, [e.id, e.at]);
    for (const f of e.file_ids ?? []) await db.query(SQL["file.delete"][0], [f, e.at]);
    n++;
  }
  if (!r.IsTruncated) break; token = r.NextContinuationToken;
}
await db.end();
console.log(`reapplied ${n} ledger entries since ${since}; the worker's cleanup removes physical data`);
