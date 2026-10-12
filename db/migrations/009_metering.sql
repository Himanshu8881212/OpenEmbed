-- Storage meter (guide 12.3): hourly samples integrated into GiB-month. Bytes counted once per workspace (blobs).
CREATE TABLE storage_samples (
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  at timestamptz NOT NULL DEFAULT now(),
  bytes bigint NOT NULL CHECK (bytes >= 0),
  PRIMARY KEY (workspace_id, at)
);
ALTER TABLE storage_samples ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant ON storage_samples USING (workspace_id = kb_ws()) WITH CHECK (workspace_id = kb_ws());
GRANT SELECT, INSERT ON storage_samples TO kb_api, kb_worker;
