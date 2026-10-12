-- Second validated profile: same pinned model/runtime, finer text segmentation. A preparation change is a new
-- immutable profile (guide 15.5); stores move to it only through reindex + promotion.
INSERT INTO embedding_profiles (id, model, revision, dims, normalize, dtype, query_prompt, document_template, preparation, adapter_version)
VALUES ('eg2-914f7f8-fp32-p2', 'google/embeddinggemma-2', '914f7f89142e33e77833254d9c9b90c3cef7303b', 768, true, 'float32',
  'task: search result | query: ', 'title: {title} | text: {content}',
  '{"text":{"max_chars":800,"overlap_chars":100},"pdf":{"text_min_chars":20,"render_dpi":110},"image":{"max_soft_tokens":280},
    "audio":{"sample_rate":16000,"segment_seconds":30},"video":{"fps":1,"segment_seconds":30,"streams":["video"]},"max_tokens":8192}',
  'kbpy-1');
INSERT INTO model_aliases (alias, profile_id, purpose) VALUES
  ('eg2-914f7f8-fp32-p2-query', 'eg2-914f7f8-fp32-p2', 'query'),
  ('eg2-914f7f8-fp32-p2-document', 'eg2-914f7f8-fp32-p2', 'document');

-- Source connectors with scheduled sync (supported type: http_manifest).
CREATE TABLE connectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  store_id uuid NOT NULL REFERENCES stores ON DELETE CASCADE,
  type text NOT NULL CHECK (type IN ('http_manifest')),
  config jsonb NOT NULL,
  interval_minutes int NOT NULL CHECK (interval_minutes >= 5),
  next_run_at timestamptz NOT NULL DEFAULT now(),
  last_job_id uuid,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
ALTER TABLE connectors ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant ON connectors USING (workspace_id = kb_ws()) WITH CHECK (workspace_id = kb_ws());
GRANT SELECT, INSERT, UPDATE, DELETE ON connectors TO kb_api, kb_worker;

-- Scheduler entry: due connectors across tenants (ids only), so the worker can then act inside each tenant context.
CREATE FUNCTION kb_due_connectors() RETURNS TABLE (id uuid, workspace_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT c.id, c.workspace_id FROM connectors c JOIN stores s ON s.id = c.store_id AND s.deleted_at IS NULL
  WHERE c.deleted_at IS NULL AND c.next_run_at <= now() $$;
REVOKE EXECUTE ON FUNCTION kb_due_connectors FROM PUBLIC, kb_api;
GRANT EXECUTE ON FUNCTION kb_due_connectors TO kb_worker;
