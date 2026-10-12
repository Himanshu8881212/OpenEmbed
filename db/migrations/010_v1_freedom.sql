-- 1) Workspace-defined embedding profiles (custom chunking). Global profiles keep workspace_id NULL.
ALTER TABLE embedding_profiles ADD COLUMN workspace_id uuid REFERENCES workspaces ON DELETE CASCADE, ADD COLUMN name text;
ALTER TABLE model_aliases ADD COLUMN workspace_id uuid REFERENCES workspaces ON DELETE CASCADE;
ALTER TABLE embedding_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_aliases ENABLE ROW LEVEL SECURITY;
CREATE POLICY visible ON embedding_profiles FOR SELECT USING (workspace_id IS NULL OR workspace_id = kb_ws());
CREATE POLICY own ON embedding_profiles FOR INSERT WITH CHECK (workspace_id = kb_ws());
CREATE POLICY visible ON model_aliases FOR SELECT USING (workspace_id IS NULL OR workspace_id = kb_ws());
CREATE POLICY own ON model_aliases FOR INSERT WITH CHECK (workspace_id = kb_ws());
GRANT INSERT ON embedding_profiles, model_aliases TO kb_api;

-- 2) Request rate limiting: fixed one-minute windows per principal; limit from the workspace plan.
CREATE TABLE rate_windows (
  principal text NOT NULL,
  window_start timestamptz NOT NULL,
  hits int NOT NULL,
  PRIMARY KEY (principal, window_start)
);
CREATE FUNCTION kb_rate_hit(p_workspace uuid, p_principal text, p_default int)
RETURNS TABLE (allowed boolean, lim int, remaining int, reset_seconds int)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE w timestamptz := date_trunc('minute', now()); n int; l int;
BEGIN
  SELECT coalesce((plan->'limits'->>'requests_per_minute')::int, p_default) INTO l FROM workspaces WHERE id = p_workspace;
  l := coalesce(l, p_default);
  INSERT INTO rate_windows AS r (principal, window_start, hits) VALUES (p_principal, w, 1)
  ON CONFLICT (principal, window_start) DO UPDATE SET hits = r.hits + 1 RETURNING r.hits INTO n;
  IF random() < 0.01 THEN DELETE FROM rate_windows WHERE window_start < now() - interval '10 minutes'; END IF;
  RETURN QUERY SELECT n <= l, l, greatest(l - n, 0), (60 - extract(second FROM now())::int);
END $$;
REVOKE ALL ON rate_windows FROM PUBLIC, kb_api, kb_worker;
REVOKE EXECUTE ON FUNCTION kb_rate_hit FROM PUBLIC, kb_worker;
GRANT EXECUTE ON FUNCTION kb_rate_hit TO kb_api;

-- 3) Live views may derive from other views (DAG; depth limited by the API). Membership resolves recursively,
--    snapshot pins pass through unchanged.
CREATE OR REPLACE FUNCTION kb_store_members(p_store uuid) RETURNS TABLE (file_id uuid, version_id uuid)
LANGUAGE sql STABLE AS $$
  WITH s AS (SELECT * FROM stores WHERE id = p_store AND deleted_at IS NULL),
  direct AS (
    SELECT f.id, coalesce(sf.pinned_version_id, f.current_version_id) AS v
    FROM s JOIN store_files sf ON sf.store_id = s.id JOIN files f ON f.id = sf.file_id
    WHERE s.kind IN ('material','snapshot') AND f.deleted_at IS NULL
  ),
  viewed AS (
    SELECT DISTINCT ON (f.id) f.id, pm.version_id AS v
    FROM s
    JOIN stores ps ON ps.id = ANY (ARRAY(SELECT jsonb_array_elements_text(s.definition->'parents'))::uuid[]) AND ps.deleted_at IS NULL
    CROSS JOIN LATERAL kb_store_members(ps.id) pm
    JOIN files f ON f.id = pm.file_id AND f.deleted_at IS NULL
    LEFT JOIN file_versions fv ON fv.id = pm.version_id
    WHERE s.kind = 'view'
      AND f.metadata @> coalesce(s.definition->'filter'->'metadata', '{}')
      AND (s.definition->'filter'->>'path_prefix' IS NULL OR starts_with(f.path, s.definition->'filter'->>'path_prefix'))
      AND (s.definition->'filter'->'media_types' IS NULL OR fv.media_type IN (SELECT jsonb_array_elements_text(s.definition->'filter'->'media_types')))
    ORDER BY f.id, fv.version_no DESC NULLS LAST
  )
  SELECT id, v FROM direct WHERE v IS NOT NULL
  UNION ALL
  SELECT id, v FROM viewed WHERE v IS NOT NULL
$$;
