// Copy object storage to/from a local directory (backup drill). Usage:
//   node scripts/objects.mjs export DIR        all objects except ledger/
//   node scripts/objects.mjs import DIR        restore objects (never touches ledger/)
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { GetObjectCommand, ListObjectsV2Command, PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
if (existsSync(".env")) process.loadEnvFile(".env"); // optional: containers use real environment variables
const s3 = new S3Client({ endpoint: process.env.KB_S3_ENDPOINT, region: process.env.KB_S3_REGION, forcePathStyle: true, credentials: { accessKeyId: process.env.KB_S3_ACCESS_KEY, secretAccessKey: process.env.KB_S3_SECRET_KEY } });
const Bucket = process.env.KB_S3_BUCKET;
const [mode, dir] = process.argv.slice(2);
let n = 0;
if (mode === "export") {
  for (let token; ; ) {
    const r = await s3.send(new ListObjectsV2Command({ Bucket, ContinuationToken: token }));
    for (const o of r.Contents ?? []) {
      if (o.Key.startsWith("ledger/")) continue;
      const body = Buffer.from(await (await s3.send(new GetObjectCommand({ Bucket, Key: o.Key }))).Body.transformToByteArray());
      const p = join(dir, o.Key); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, body); n++;
    }
    if (!r.IsTruncated) break; token = r.NextContinuationToken;
  }
} else if (mode === "import") {
  const walk = (d) => readdirSync(d).flatMap((x) => (statSync(join(d, x)).isDirectory() ? walk(join(d, x)) : [join(d, x)]));
  for (const p of walk(dir)) {
    const Key = relative(dir, p).split("\\").join("/");
    if (Key.startsWith("ledger/")) continue;
    await s3.send(new PutObjectCommand({ Bucket, Key, Body: readFileSync(p) })); n++;
  }
} else { console.error("usage: objects.mjs export|import DIR"); process.exit(1); }
console.log(`${mode}ed ${n} objects`);
