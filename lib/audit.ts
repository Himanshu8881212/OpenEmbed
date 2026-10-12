import type { Principal } from "./auth";
import type { Db } from "./db";

/** Audit record without customer content (ids and action metadata only). */
export const audit = (db: Db, p: Principal, action: string, target: string | null, data: Record<string, unknown> = {}) =>
  db.query("INSERT INTO audit_events (workspace_id, actor, action, target, data) VALUES ($1,$2,$3,$4,$5)", [p.workspaceId, p.actor, action, target, data]);
