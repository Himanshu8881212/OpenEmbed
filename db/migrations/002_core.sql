-- Core catalogue. Tables are owned by the migration role; apps connect as kb_api / kb_worker (RLS enforced).
CREATE EXTENSION IF NOT EXISTS vector;

-- Workspace context: transaction-local, NULL when unset => no tenant rows visible (fail closed).
CREATE FUNCTION kb_ws() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.workspace_id', true), '')::uuid $$;

CREATE TABLE workspaces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
  plan jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE identities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  issuer text NOT NULL,
  subject text NOT NULL,
  email text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (issuer, subject)
);

CREATE TABLE members (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  email text NOT NULL,
  identity_id uuid REFERENCES identities,
  role text NOT NULL CHECK (role IN ('owner','editor','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, email)
);

CREATE TABLE api_keys (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  name text NOT NULL,
  prefix text NOT NULL,
  token_hash bytea NOT NULL UNIQUE,
  scopes text[] NOT NULL CHECK (scopes <@ ARRAY['search','source:read','source:write','embeddings'] AND cardinality(scopes) > 0),
  store_ids uuid[],
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  last_used_at timestamptz
);

-- Immutable embedding profiles and aliases (global catalogue, written only by migrations).
CREATE TABLE embedding_profiles (
  id text PRIMARY KEY,
  model text NOT NULL,
  revision text NOT NULL,
  dims int NOT NULL CHECK (dims = 768),
  normalize boolean NOT NULL,
  dtype text NOT NULL CHECK (dtype IN ('float32','bfloat16')),
  query_prompt text NOT NULL,
  document_template text NOT NULL,
  preparation jsonb NOT NULL,
  embedded_metadata_fields text[] NOT NULL DEFAULT '{}',
  adapter_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE model_aliases (
  alias text PRIMARY KEY,
  profile_id text NOT NULL REFERENCES embedding_profiles,
  purpose text NOT NULL CHECK (purpose IN ('query','document')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE FUNCTION kb_immutable() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME USING ERRCODE = 'restrict_violation'; END $$;
CREATE TRIGGER profiles_immutable BEFORE UPDATE OR DELETE ON embedding_profiles FOR EACH ROW EXECUTE FUNCTION kb_immutable();
CREATE TRIGGER aliases_immutable BEFORE UPDATE OR DELETE ON model_aliases FOR EACH ROW EXECUTE FUNCTION kb_immutable();

CREATE TABLE stores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  name text NOT NULL CHECK (name ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$'),
  kind text NOT NULL DEFAULT 'material' CHECK (kind IN ('material','view','snapshot')),
  definition jsonb NOT NULL DEFAULT '{}',
  active_revision_id uuid,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE UNIQUE INDEX stores_name_uq ON stores (workspace_id, lower(name)) WHERE deleted_at IS NULL;

CREATE TABLE index_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  store_id uuid NOT NULL REFERENCES stores ON DELETE CASCADE,
  profile_id text NOT NULL REFERENCES embedding_profiles,
  state text NOT NULL CHECK (state IN ('building','ready','active','retired','failed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  promoted_at timestamptz
);
ALTER TABLE stores ADD FOREIGN KEY (active_revision_id) REFERENCES index_revisions DEFERRABLE INITIALLY DEFERRED;

-- Content-addressed originals, one physical copy per workspace.
CREATE TABLE blobs (
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  size bigint NOT NULL,
  object_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, sha256)
);

CREATE TABLE files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  path text NOT NULL,
  current_version_id uuid,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE TABLE file_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL,
  file_id uuid NOT NULL REFERENCES files ON DELETE CASCADE,
  version_no int NOT NULL,
  sha256 text NOT NULL,
  size bigint NOT NULL,
  filename text NOT NULL,
  media_type text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (file_id, version_no),
  FOREIGN KEY (workspace_id, sha256) REFERENCES blobs
);
ALTER TABLE files ADD FOREIGN KEY (current_version_id) REFERENCES file_versions DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE store_files (
  workspace_id uuid NOT NULL,
  store_id uuid NOT NULL REFERENCES stores ON DELETE CASCADE,
  file_id uuid NOT NULL REFERENCES files ON DELETE CASCADE,
  pinned_version_id uuid REFERENCES file_versions,
  added_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (store_id, file_id)
);
CREATE INDEX store_files_file ON store_files (file_id);

CREATE TABLE segments (
  id uuid PRIMARY KEY,                 -- uuid5(file_version, profile, ordinal): retries are idempotent
  workspace_id uuid NOT NULL,
  file_version_id uuid NOT NULL REFERENCES file_versions ON DELETE CASCADE,
  profile_id text NOT NULL REFERENCES embedding_profiles,
  ordinal int NOT NULL,
  modality text NOT NULL CHECK (modality IN ('text','image','audio','video')),
  location jsonb NOT NULL,
  content text,
  media_key text,
  token_count int NOT NULL,
  embedding vector(768) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (file_version_id, profile_id, ordinal)
);
CREATE INDEX segments_hnsw ON segments USING hnsw (embedding vector_cosine_ops);

CREATE TABLE upload_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  store_id uuid REFERENCES stores,
  created_by text,
  state text NOT NULL DEFAULT 'open' CHECK (state IN ('open','committed','abandoned','expired')),
  commit_request_hash text,
  job_id uuid,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE upload_files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL,
  session_id uuid NOT NULL REFERENCES upload_sessions ON DELETE CASCADE,
  path text NOT NULL,
  size bigint NOT NULL CHECK (size >= 0),
  sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  media_type text NOT NULL,
  replaces_file_id uuid REFERENCES files,
  part_size int NOT NULL,
  s3_upload_id text,
  object_key text NOT NULL,
  UNIQUE (session_id, path)
);
CREATE TABLE upload_parts (
  workspace_id uuid NOT NULL,
  upload_file_id uuid NOT NULL REFERENCES upload_files ON DELETE CASCADE,
  part_no int NOT NULL,
  size bigint NOT NULL,
  etag text NOT NULL,
  PRIMARY KEY (upload_file_id, part_no)
);

CREATE TABLE jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  store_id uuid REFERENCES stores,
  kind text NOT NULL,
  state text NOT NULL DEFAULT 'queued' CHECK (state IN ('queued','running','cancel_requested','completed','completed_with_errors','failed','cancelled')),
  params jsonb NOT NULL DEFAULT '{}',
  result jsonb,
  idempotency_key text,
  request_hash text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  UNIQUE (workspace_id, idempotency_key)
);
CREATE TABLE job_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL,
  job_id uuid NOT NULL REFERENCES jobs ON DELETE CASCADE,
  path text,
  upload_file_id uuid REFERENCES upload_files ON DELETE SET NULL,
  file_id uuid REFERENCES files ON DELETE SET NULL,
  file_version_id uuid REFERENCES file_versions ON DELETE SET NULL,
  state text NOT NULL DEFAULT 'queued' CHECK (state IN ('queued','running','succeeded','failed','cancelled')),
  retryable boolean NOT NULL DEFAULT false,
  error_code text,
  error_message text,
  attempts int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX job_items_job ON job_items (job_id);

CREATE TABLE usage_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  kind text NOT NULL,              -- index_text_tokens | index_media_tokens | query_text_tokens | query_media_tokens | query_requests
  quantity bigint NOT NULL CHECK (quantity >= 0),
  idem_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, idem_key)
);

CREATE TABLE audit_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  actor text NOT NULL,
  action text NOT NULL,
  target text,
  data jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE query_assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES workspaces ON DELETE CASCADE,
  media_type text NOT NULL,
  size bigint NOT NULL,
  object_key text NOT NULL,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Row security on every tenant table.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['members','api_keys','stores','index_revisions','blobs','files','file_versions','store_files',
    'segments','upload_sessions','upload_files','upload_parts','jobs','job_items','usage_events','audit_events','query_assets'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY tenant ON %I USING (workspace_id = kb_ws()) WITH CHECK (workspace_id = kb_ws())', t);
  END LOOP;
END $$;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant ON workspaces USING (id = kb_ws()) WITH CHECK (id = kb_ws());

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kb_api, kb_worker;
REVOKE INSERT, UPDATE, DELETE ON embedding_profiles, model_aliases, identities FROM kb_api, kb_worker;
REVOKE INSERT, DELETE ON workspaces FROM kb_api, kb_worker;
REVOKE ALL ON identities FROM kb_worker;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO kb_api, kb_worker;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO kb_api, kb_worker;

-- Narrow cross-tenant entry points (SECURITY DEFINER, fixed search_path).
CREATE FUNCTION kb_login(p_issuer text, p_subject text, p_email text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v uuid;
BEGIN
  INSERT INTO identities (issuer, subject, email) VALUES (p_issuer, p_subject, lower(p_email))
  ON CONFLICT (issuer, subject) DO UPDATE SET email = excluded.email RETURNING id INTO v;
  -- accept pending invitations addressed to this verified email
  IF p_email IS NOT NULL THEN
    UPDATE members SET identity_id = v WHERE identity_id IS NULL AND email = lower(p_email);
  END IF;
  RETURN v;
END $$;

CREATE FUNCTION kb_memberships(p_identity uuid)
RETURNS TABLE (workspace_id uuid, workspace_name text, role text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT w.id, w.name, m.role FROM members m JOIN workspaces w ON w.id = m.workspace_id
  WHERE m.identity_id = p_identity ORDER BY w.created_at
$$;

CREATE FUNCTION kb_create_workspace(p_identity uuid, p_name text, p_plan jsonb) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v uuid; e text;
BEGIN
  SELECT email INTO e FROM identities WHERE id = p_identity;
  IF NOT FOUND THEN RAISE EXCEPTION 'unknown identity'; END IF;
  INSERT INTO workspaces (name, plan) VALUES (p_name, p_plan) RETURNING id INTO v;
  INSERT INTO members (workspace_id, email, identity_id, role) VALUES (v, coalesce(e, p_identity::text), p_identity, 'owner');
  RETURN v;
END $$;

CREATE FUNCTION kb_lookup_api_key(p_hash bytea)
RETURNS TABLE (id uuid, workspace_id uuid, scopes text[], store_ids uuid[], created_by uuid)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  UPDATE api_keys SET last_used_at = now()
  WHERE token_hash = p_hash AND revoked_at IS NULL
  RETURNING id, workspace_id, scopes, store_ids, created_by
$$;

-- Worker entry: map a job id to its workspace without granting cross-tenant reads.
CREATE FUNCTION kb_job_workspace(p_job uuid) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$ SELECT workspace_id FROM jobs WHERE id = p_job $$;

REVOKE EXECUTE ON FUNCTION kb_login, kb_memberships, kb_create_workspace, kb_lookup_api_key FROM PUBLIC, kb_worker;
REVOKE EXECUTE ON FUNCTION kb_job_workspace FROM PUBLIC, kb_api;
GRANT EXECUTE ON FUNCTION kb_login, kb_memberships, kb_create_workspace, kb_lookup_api_key TO kb_api;
GRANT EXECUTE ON FUNCTION kb_job_workspace TO kb_worker;

-- Procrastinate queue: both roles defer; the worker consumes.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kb_worker;
REVOKE ALL ON identities FROM kb_worker;
GRANT SELECT, INSERT ON procrastinate_jobs, procrastinate_events TO kb_api;
REVOKE INSERT, UPDATE, DELETE ON embedding_profiles, model_aliases FROM kb_worker;

-- Initial validated profile (EmbeddingGemma 2, docs/decisions.md D10-D13).
INSERT INTO embedding_profiles (id, model, revision, dims, normalize, dtype, query_prompt, document_template, preparation, adapter_version)
VALUES ('eg2-914f7f8-fp32-p1', 'google/embeddinggemma-2', '914f7f89142e33e77833254d9c9b90c3cef7303b', 768, true, 'float32',
  'task: search result | query: ', 'title: {title} | text: {content}',
  '{"text":{"max_chars":1600,"overlap_chars":200},"pdf":{"text_min_chars":20,"render_dpi":110},"image":{"max_soft_tokens":280},
    "audio":{"sample_rate":16000,"segment_seconds":30},"video":{"fps":1,"segment_seconds":30,"streams":["video"]},"max_tokens":8192}',
  'kbpy-1');
INSERT INTO model_aliases (alias, profile_id, purpose) VALUES
  ('eg2-914f7f8-fp32-p1-query', 'eg2-914f7f8-fp32-p1', 'query'),
  ('eg2-914f7f8-fp32-p1-document', 'eg2-914f7f8-fp32-p1', 'document');
