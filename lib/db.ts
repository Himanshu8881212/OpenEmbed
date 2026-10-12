import pg from "pg";
import { config } from "./config";

// Timestamps stay full-precision strings (microseconds): JS Date would truncate to milliseconds and pagination
// cursors built from it could skip rows created within the same millisecond.
pg.types.setTypeParser(1184, (v) => v); // timestamptz
pg.types.setTypeParser(1114, (v) => v); // timestamp

// Connects as kb_api (non-owner): row security applies to every tenant table.
const g = globalThis as unknown as { kbPool?: pg.Pool };
const real = () => (g.kbPool ??= new pg.Pool({ connectionString: config().KB_DATABASE_URL, max: Number(process.env.KB_DB_POOL_MAX ?? 10) }));
/** Lazy: created on first use, so builds never need runtime configuration. */
export const pool = new Proxy({} as pg.Pool, { get: (_, k) => { const p = real() as any; const v = p[k]; return typeof v === "function" ? v.bind(p) : v; } });

export type Db = pg.PoolClient;

/** Run fn in one transaction with the workspace context set transaction-locally (safe under pooling). */
export async function tx<T>(workspaceId: string | null, fn: (db: Db) => Promise<T>): Promise<T> {
  const c = await pool.connect();
  try {
    await c.query("BEGIN");
    if (workspaceId) await c.query("SELECT set_config('app.workspace_id', $1, true)", [workspaceId]);
    const r = await fn(c);
    await c.query("COMMIT");
    return r;
  } catch (e) {
    await c.query("ROLLBACK").catch(() => {});
    throw e;
  } finally {
    c.release();
  }
}

export async function one<T = any>(db: Db, sql: string, params: unknown[] = []): Promise<T | undefined> {
  return (await db.query(sql, params)).rows[0];
}
export async function all<T = any>(db: Db, sql: string, params: unknown[] = []): Promise<T[]> {
  return (await db.query(sql, params)).rows;
}
