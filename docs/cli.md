# CLI reference (kb 0.1.0)

Generated from `kb help` (`node cli/kb.ts help <command>`). Every command calls the HTTP API shown; local-only commands make no request.

```
kb 0.1.0 — Multimodal Knowledge Store CLI

Usage: kb <command> [args]   (kb help <command> for details)

  kb config set base-url URL                                               Store local CLI configuration (no network)
  kb config show                                                           Show local configuration
  kb auth login                                                            Authenticate a human user with the browser device flow
  kb auth status [--json]                                                  Show the current identity and workspace
  kb auth logout                                                           Remove local credentials
  kb workspaces list [--json]                                              List accessible workspaces
  kb workspaces create NAME                                                Create a workspace (you become owner) and select it
  kb workspaces use ID                                                     Select the workspace for later commands
  kb members list                                                          List workspace members
  kb members add EMAIL --role owner|editor|viewer                          Invite a member (owner only)
  kb members update MEMBER_ID --role ROLE                                  Change a member role (owner only)
  kb members remove MEMBER_ID                                              Remove a member (owner only)
  kb stores create NAME [--profile ID]                                     Create an empty material store
  kb stores list [--json]                                                  List accessible stores
  kb stores info STORE [--json]                                            Inspect state, profile and size
  kb stores rename STORE NEW_NAME                                          Rename (ID and connections unchanged)
  kb stores delete STORE --sources unshared|keep [--yes] [--wait]          Preview, then delete a store
  kb stores merge A B [...] --into NAME [--wait]                           Later release: combine compatible stores into a new store without re-embedding
  kb stores derive STORE [STORE...] --name NAME --mode view|snapshot --filter @filter.json [--wait] Later release: create a live view or snapshot over parent stores
  kb stores reindex STORE --profile ID [--wait]                            Later release: build a new index with another profile (not yet active)
  kb stores promote STORE REVISION_ID                                      Later release: activate a ready index revision (also used for rollback)
  kb ingest STORE ./folder [--wait] [--yes] [--json]                       Upload the folder's supported files (relative paths kept; symlinks/hidden/unsupported ignored and listed), commit, and start indexing
  kb jobs status JOB_ID [--wait] [--json]                                  Job state and per-item counts
  kb jobs list [--json]                                                    Recent jobs
  kb jobs items JOB_ID [--state failed] [--json]                           Per-file results
  kb jobs retry JOB_ID [--wait]                                            Retry retryable failed items as a new job
  kb jobs cancel JOB_ID [--wait]                                           Request safe cancellation; published items remain
  kb files list STORE [--json]                                             Sources assigned to a store
  kb files inspect FILE_ID [--segments] [--json]                           Current version, status, stores, segment count (and segments)
  kb files tag FILE_ID --set KEY=VALUE [--set …] [--unset KEY]             Update source metadata (merge)
  kb files replace FILE_ID ./file [--wait]                                 Upload a replacement version; the old version stays searchable until the new one publishes
  kb files remove STORE FILE_ID                                            Remove the source from one store only
  kb files delete FILE_ID [--yes] [--wait]                                 Preview, then delete the source everywhere (including snapshots)
  kb files download FILE_ID [-o PATH]                                      Download the original bytes (permission required)
  kb search STORE QUERY [--limit N] [--filter @filter.json|JSON] [--image|--audio|--video PATH] [--json] Retrieve ranked evidence with source locations
  kb connect STORE [--language python|javascript|curl] [--json]            Print connection details and runnable code for an application
  kb keys create --store STORE [--scope search,source:read] [--name NAME]  Create a restricted application key
  kb keys list [--json]                                                    List API keys (no secrets)
  kb keys revoke KEY_ID                                                    Revoke a key (effective immediately)
  kb usage show [--json]                                                   Storage by category and indexing/query allowances
  kb models list [--json]                                                  Validated model aliases
  kb uploads status SESSION_ID [--json]                                    Inspect an upload session (received parts)
  kb uploads abandon SESSION_ID                                            Abandon an open upload session

Environment: KB_BASE_URL, KB_API_KEY (scripts), KB_WORKSPACE, KB_CONFIG_DIR.
```

## kb config set

```
kb config set base-url URL | workspace ID

Store local CLI configuration (no network).
API: local only

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb config show

```
kb config show

Show local configuration.
API: local only

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb auth login

```
kb auth login

Authenticate a human user with the browser device flow. Prerequisite: base URL configured; a workspace invitation or account.
API: POST /v1/auth/device-sessions, POST /v1/auth/token, GET /v1/me

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb auth status

```
kb auth status [--json]

Show the current identity and workspace.
API: GET /v1/me

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb auth logout

```
kb auth logout

Remove local credentials.
API: local only

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb workspaces list

```
kb workspaces list [--json]

List accessible workspaces.
API: GET /v1/workspaces

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb workspaces create

```
kb workspaces create NAME

Create a workspace (you become owner) and select it.
API: POST /v1/workspaces

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb workspaces use

```
kb workspaces use ID

Select the workspace for later commands.
API: local only

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb members list

```
kb members list

List workspace members.
API: GET /v1/workspaces/{id}/members

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb members add

```
kb members add EMAIL --role owner|editor|viewer

Invite a member (owner only).
API: POST /v1/workspaces/{id}/members

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb members update

```
kb members update MEMBER_ID --role ROLE

Change a member role (owner only).
API: PATCH /v1/workspaces/{id}/members/{member_id}

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb members remove

```
kb members remove MEMBER_ID

Remove a member (owner only).
API: DELETE /v1/workspaces/{id}/members/{member_id}

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb stores create

```
kb stores create NAME [--profile ID]

Create an empty material store. Prerequisite: editor role.
API: POST /v1/stores

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb stores list

```
kb stores list [--json]

List accessible stores.
API: GET /v1/stores

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb stores info

```
kb stores info STORE [--json]

Inspect state, profile and size.
API: GET /v1/stores/{id}, GET /v1/stores/{id}/stats

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb stores rename

```
kb stores rename STORE NEW_NAME

Rename (ID and connections unchanged).
API: PATCH /v1/stores/{id}

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb stores delete

```
kb stores delete STORE --sources unshared|keep [--yes] [--wait]

Preview, then delete a store. --sources unshared also deletes sources no other store uses.
API: POST /v1/stores/{id}/deletion-previews, DELETE /v1/stores/{id}

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb stores merge

```
kb stores merge A B [...] --into NAME [--wait]

Later release: combine compatible stores into a new store without re-embedding.
API: POST /v1/store-merges

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb stores derive

```
kb stores derive STORE [STORE...] --name NAME --mode view|snapshot --filter @filter.json [--wait]

Later release: create a live view or snapshot over parent stores.
API: POST /v1/stores/{id}/derivations

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb stores reindex

```
kb stores reindex STORE --profile ID [--wait]

Later release: build a new index with another profile (not yet active).
API: POST /v1/stores/{id}/reindex-jobs

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb stores promote

```
kb stores promote STORE REVISION_ID

Later release: activate a ready index revision (also used for rollback).
API: POST /v1/stores/{id}/index-promotions

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb ingest

```
kb ingest STORE ./folder [--wait] [--yes] [--json] | kb ingest --resume SESSION_ID [--wait]

Upload the folder's supported files (relative paths kept; symlinks/hidden/unsupported ignored and listed), commit, and start indexing. Interrupted uploads resume with --resume.
API: POST /v1/upload-sessions, PUT …/parts/{n}, POST …/commit, GET /v1/jobs/{id}

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb jobs status

```
kb jobs status JOB_ID [--wait] [--json]

Job state and per-item counts. --wait exits nonzero on failure/partial completion.
API: GET /v1/jobs/{id}

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb jobs list

```
kb jobs list [--json]

Recent jobs.
API: GET /v1/jobs

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb jobs items

```
kb jobs items JOB_ID [--state failed] [--json]

Per-file results.
API: GET /v1/jobs/{id}/items

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb jobs retry

```
kb jobs retry JOB_ID [--wait]

Retry retryable failed items as a new job.
API: POST /v1/jobs/{id}/retry

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb jobs cancel

```
kb jobs cancel JOB_ID [--wait]

Request safe cancellation; published items remain.
API: POST /v1/jobs/{id}/cancel

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb files list

```
kb files list STORE [--json]

Sources assigned to a store.
API: GET /v1/stores/{id}/files

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb files inspect

```
kb files inspect FILE_ID [--segments] [--json]

Current version, status, stores, segment count (and segments).
API: GET /v1/files/{id}, GET /v1/files/{id}/segments

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb files tag

```
kb files tag FILE_ID --set KEY=VALUE [--set …] [--unset KEY]

Update source metadata (merge).
API: PATCH /v1/files/{id}

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb files replace

```
kb files replace FILE_ID ./file [--wait]

Upload a replacement version; the old version stays searchable until the new one publishes.
API: POST /v1/upload-sessions, PUT parts, POST commit, POST /v1/files/{id}/revisions

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb files remove

```
kb files remove STORE FILE_ID

Remove the source from one store only.
API: DELETE /v1/stores/{id}/files/{file_id}

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb files delete

```
kb files delete FILE_ID [--yes] [--wait]

Preview, then delete the source everywhere (including snapshots).
API: POST /v1/files/{id}/deletion-previews, DELETE /v1/files/{id}?scope=workspace

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb files download

```
kb files download FILE_ID [-o PATH]

Download the original bytes (permission required).
API: GET /v1/files/{id}/content

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb search

```
kb search STORE QUERY [--limit N] [--filter @filter.json|JSON] [--image|--audio|--video PATH] [--json]

Retrieve ranked evidence with source locations. Scores rank results; they are not answer confidence.
API: POST /v1/stores/{id}/search (+ POST /v1/query-assets for media)

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb connect

```
kb connect STORE [--language python|javascript|curl] [--json]

Print connection details and runnable code for an application. The code reads KNOWLEDGE_API_KEY.
API: GET /v1/stores/{id}/connection

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb keys create

```
kb keys create --store STORE [--scope search,source:read] [--name NAME]

Create a restricted application key. The secret is shown once.
API: POST /v1/api-keys

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb keys list

```
kb keys list [--json]

List API keys (no secrets).
API: GET /v1/api-keys

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb keys revoke

```
kb keys revoke KEY_ID

Revoke a key (effective immediately).
API: DELETE /v1/api-keys/{id}

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb usage show

```
kb usage show [--json]

Storage by category and indexing/query allowances.
API: GET /v1/usage

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb models list

```
kb models list [--json]

Validated model aliases.
API: GET /v1/models

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb uploads status

```
kb uploads status SESSION_ID [--json]

Inspect an upload session (received parts).
API: GET /v1/upload-sessions/{id}

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb uploads abandon

```
kb uploads abandon SESSION_ID

Abandon an open upload session.
API: DELETE /v1/upload-sessions/{id}

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```


## kb stores split

```
kb stores split STORE --field KEY [--mode view|snapshot] [--prefix NAME]

Create one live view (or snapshot) per value of a metadata field, reusing existing vectors.
API: POST /v1/stores/{id}/splits

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb stores export

```
kb stores export STORE [-o FILE.jsonl] [--no-embeddings]

Export indexed segments (source, location, text, embedding) as NDJSON.
API: GET /v1/stores/{id}/export

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb profiles list

```
kb profiles list [--json]

Embedding profiles available to this workspace (global and custom).
API: GET /v1/embedding-profiles

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```

## kb profiles create

```
kb profiles create NAME --max-chars N --overlap N [--audio-seconds N] [--video-seconds N]

Create an immutable custom segmentation profile; use it with stores create --profile or stores reindex.
API: POST /v1/embedding-profiles

Common: --json prints machine-readable results on stdout (progress goes to stderr). Exit codes: 0 ok, 1 error, 3 partial, 4 failed, 5 cancelled.
```
