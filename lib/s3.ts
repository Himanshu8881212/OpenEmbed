import { S3Client } from "@aws-sdk/client-s3";
import { config } from "./config";

const g = globalThis as unknown as { kbS3?: S3Client };
const real = () => (g.kbS3 ??= new S3Client({
  endpoint: config().KB_S3_ENDPOINT,
  region: config().KB_S3_REGION,
  forcePathStyle: true,
  credentials: { accessKeyId: config().KB_S3_ACCESS_KEY, secretAccessKey: config().KB_S3_SECRET_KEY },
}));
/** Lazy: created on first use, so builds never need runtime configuration. */
export const s3 = new Proxy({} as S3Client, { get: (_, k) => { const c = real() as any; const v = c[k]; return typeof v === "function" ? v.bind(c) : v; } });
export const bucket = () => config().KB_S3_BUCKET;
