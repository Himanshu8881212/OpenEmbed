-- PL/pgSQL (never inlined) so the recursion for nested views happens at run time only (SQL-function inlining recursed at plan time).
CREATE OR REPLACE FUNCTION kb_store_members(p_store uuid) RETURNS TABLE (file_id uuid, version_id uuid)
LANGUAGE plpgsql STABLE AS $$
DECLARE s stores;
BEGIN
  SELECT * INTO s FROM stores WHERE id = p_store AND deleted_at IS NULL;
  IF NOT FOUND THEN RETURN; END IF;
  IF s.kind IN ('material', 'snapshot') THEN
    RETURN QUERY
      SELECT f.id, coalesce(sf.pinned_version_id, f.current_version_id)
      FROM store_files sf JOIN files f ON f.id = sf.file_id
      WHERE sf.store_id = p_store AND f.deleted_at IS NULL AND coalesce(sf.pinned_version_id, f.current_version_id) IS NOT NULL;
  ELSE
    RETURN QUERY
      SELECT DISTINCT ON (f.id) f.id, pm.version_id
      FROM stores ps
      CROSS JOIN LATERAL kb_store_members(ps.id) pm
      JOIN files f ON f.id = pm.file_id AND f.deleted_at IS NULL
      LEFT JOIN file_versions fv ON fv.id = pm.version_id
      WHERE ps.id = ANY (ARRAY(SELECT jsonb_array_elements_text(s.definition->'parents'))::uuid[]) AND ps.deleted_at IS NULL
        AND pm.version_id IS NOT NULL
        AND f.metadata @> coalesce(s.definition->'filter'->'metadata', '{}')
        AND (s.definition->'filter'->>'path_prefix' IS NULL OR starts_with(f.path, s.definition->'filter'->>'path_prefix'))
        AND (s.definition->'filter'->'media_types' IS NULL OR fv.media_type IN (SELECT jsonb_array_elements_text(s.definition->'filter'->'media_types')))
      ORDER BY f.id, fv.version_no DESC NULLS LAST;
  END IF;
END $$;
