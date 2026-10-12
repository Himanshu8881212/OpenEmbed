import type { Db } from "./db";

/**
 * Enqueue procrastinate tasks inside the caller's transaction (job rows and queue messages commit atomically).
 * Task names match py/kbpy/worker.py.
 */
export async function defer(db: Db, task: string, args: Record<string, unknown>[], queue = "ingest", lock: string | null = null) {
  if (!args.length) return;
  await db.query(
    `SELECT procrastinate_defer_jobs_v1(array_agg(ROW($1::varchar, $2::varchar, 0, $3::text, NULL::text, a, NULL::timestamptz)::procrastinate_job_to_defer_v1))
       FROM jsonb_array_elements($4::jsonb) a`,
    [queue, task, lock, JSON.stringify(args)],
  );
}
