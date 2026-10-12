-- Aggregate operational gauges for /metrics (counts only, no tenant data).
CREATE FUNCTION kb_metrics() RETURNS TABLE (name text, labels text, value double precision)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT 'kb_workspaces', '', count(*)::float8 FROM workspaces
  UNION ALL SELECT 'kb_stores', 'kind="' || kind || '"', count(*)::float8 FROM stores WHERE deleted_at IS NULL GROUP BY kind
  UNION ALL SELECT 'kb_segments', '', count(*)::float8 FROM segments
  UNION ALL SELECT 'kb_blob_bytes', '', coalesce(sum(size), 0)::float8 FROM blobs
  UNION ALL SELECT 'kb_jobs', 'state="' || state || '"', count(*)::float8 FROM jobs GROUP BY state
  UNION ALL SELECT 'kb_job_items', 'state="' || state || '"', count(*)::float8 FROM job_items GROUP BY state
  UNION ALL SELECT 'kb_queue_tasks', 'queue="' || queue_name || '",status="' || status || '"', count(*)::float8 FROM procrastinate_jobs WHERE status IN ('todo','doing') GROUP BY queue_name, status
  UNION ALL SELECT 'kb_workers_alive', '', count(*)::float8 FROM procrastinate_workers WHERE last_heartbeat > now() - interval '1 minute'
$$;
REVOKE EXECUTE ON FUNCTION kb_metrics FROM PUBLIC, kb_worker;
GRANT EXECUTE ON FUNCTION kb_metrics TO kb_api;
