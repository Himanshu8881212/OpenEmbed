import { randomUUID } from "node:crypto";
import { PutObjectCommand } from "@aws-sdk/client-s3";
import { bucket, s3 } from "./s3";

/**
 * Append-only record of deletions and revocations under `ledger/` in object storage. Restores never restore this
 * prefix; `scripts/reapply-deletions.mjs` replays entries newer than the backup so a restored service cannot expose
 * deleted material or revived credentials. Written inside the deleting transaction before COMMIT: if the write fails,
 * the deletion fails (never "deleted but unrecorded").
 */
export async function ledger(kind: "file.delete" | "store.delete" | "api_key.revoke" | "member.remove", workspaceId: string, id: string, data: Record<string, unknown> = {}) {
  const at = new Date().toISOString();
  await s3.send(new PutObjectCommand({
    Bucket: bucket(), Key: `ledger/${at}-${randomUUID()}.json`, ContentType: "application/json",
    Body: JSON.stringify({ kind, workspace_id: workspaceId, id, at, ...data }),
  }));
}
