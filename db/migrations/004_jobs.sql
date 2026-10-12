-- Single source of truth for job terminal state (used by API cancel and worker item completion).
CREATE FUNCTION kb_finalize_job(p_job uuid) RETURNS text LANGUAGE plpgsql AS $$
DECLARE j jobs; c record; s text;
BEGIN
  SELECT * INTO j FROM jobs WHERE id = p_job FOR UPDATE;
  IF NOT FOUND THEN RETURN NULL; END IF;
  IF j.state IN ('completed','completed_with_errors','failed','cancelled') THEN RETURN j.state; END IF;
  SELECT count(*) FILTER (WHERE state IN ('queued','running')) AS open,
         count(*) FILTER (WHERE state = 'running') AS running,
         count(*) FILTER (WHERE state = 'succeeded') AS ok,
         count(*) FILTER (WHERE state = 'failed') AS bad,
         count(*) FILTER (WHERE state = 'cancelled') AS cx
    INTO c FROM job_items WHERE job_id = p_job;
  IF c.open > 0 THEN
    IF j.state = 'queued' AND (c.running > 0 OR c.ok + c.bad > 0) THEN
      UPDATE jobs SET state = 'running', updated_at = now() WHERE id = p_job;
      RETURN 'running';
    END IF;
    RETURN j.state;
  END IF;
  s := CASE WHEN j.state = 'cancel_requested' OR c.cx > 0 THEN 'cancelled'
            WHEN c.bad = 0 THEN 'completed'
            WHEN c.ok > 0 THEN 'completed_with_errors'
            ELSE 'failed' END;
  UPDATE jobs SET state = s, finished_at = now(), updated_at = now() WHERE id = p_job;
  RETURN s;
END $$;
GRANT EXECUTE ON FUNCTION kb_finalize_job TO kb_api, kb_worker;
