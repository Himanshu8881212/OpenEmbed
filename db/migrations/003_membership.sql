-- Resolved membership of a store: (file_id, version_id) visible to search.
--   material: explicit store_files rows, current published version
--   snapshot: explicit rows with pinned versions
--   view:     live filter over parent stores (material or snapshot), evaluated at query time
-- Deleted files and deleted parents never appear. SECURITY INVOKER: row security applies.
CREATE FUNCTION kb_store_members(p_store uuid) RETURNS TABLE (file_id uuid, version_id uuid)
LANGUAGE sql STABLE AS $$
  WITH s AS (SELECT * FROM stores WHERE id = p_store AND deleted_at IS NULL),
  direct AS (
    SELECT f.id, coalesce(sf.pinned_version_id, f.current_version_id) AS v
    FROM s JOIN store_files sf ON sf.store_id = s.id JOIN files f ON f.id = sf.file_id
    WHERE s.kind IN ('material','snapshot') AND f.deleted_at IS NULL
  ),
  viewed AS (
    SELECT DISTINCT ON (f.id) f.id, coalesce(sf.pinned_version_id, f.current_version_id) AS v
    FROM s
    JOIN stores ps ON ps.id = ANY (ARRAY(SELECT jsonb_array_elements_text(s.definition->'parents'))::uuid[]) AND ps.deleted_at IS NULL
    JOIN store_files sf ON sf.store_id = ps.id
    JOIN files f ON f.id = sf.file_id AND f.deleted_at IS NULL
    LEFT JOIN file_versions fv ON fv.id = coalesce(sf.pinned_version_id, f.current_version_id)
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
GRANT EXECUTE ON FUNCTION kb_store_members TO kb_api, kb_worker;
