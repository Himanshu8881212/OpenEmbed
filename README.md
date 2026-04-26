# EMBEd

Self-hosted multimodal embeddings powered by **Meta Perception Encoder**. Upload text, images, audio, video, and PDFs — search across every modality from one query.

## Quick Start

```bash
# 1. Configure (admin key gates create/list/delete vault routes)
cp .env.example .env
# edit .env and set ADMIN_API_KEY to a strong random value

# 2. Install & run (Python 3.12 recommended)
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
python -m app.main
```

Open **<http://localhost:8000>**

> First boot downloads ~6GB of Perception Encoder weights (PE-Core-L14-336 + PE-AV-Large) and ~570MB of the BGE-reranker-v2-m3. Subsequent boots are fast.

## Supported Modalities

| Modality | Formats |
|----------|---------|
| Text | `.txt`, `.md` |
| Image | `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp` |
| Video | `.mp4`, `.mov` |
| Audio | `.mp3`, `.wav`, `.flac`, `.m4a`, `.ogg` |
| Document | `.pdf` |

## API

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/health` | none | Liveness + memory |
| `POST` | `/api/stores` | admin | Create vault, returns one-time API key |
| `GET` | `/api/stores` | admin | List vaults |
| `GET` | `/api/stores/{name}` | vault or admin | Vault detail |
| `POST` | `/api/stores/{name}/rotate-key` | vault or admin | Issue a fresh per-vault key |
| `DELETE` | `/api/stores/{name}` | vault or admin | Delete vault |
| `POST` | `/api/embed` | vault or admin | Embed text or file |
| `POST` | `/api/embed/batch` | vault or admin | Embed multiple files |
| `POST` | `/api/search` | vault or admin | Search (text or file) |
| `POST` | `/api/retrieve` | vault or admin | RAG-shaped JSON retrieval |
| `GET` | `/api/files/{store}/{name}` | vault or admin | Auth-gated file fetch |
| `GET` | `/api/formats` | none | Supported formats |

Auth is via the `X-API-Key` header. `/api/files/...` also accepts `?api_key=...` so `<img>`/`<video>` tags work. Full OpenAPI docs at `/docs`.

### Filtering retrieval results

Two thresholds control how strict retrieval is. Both are optional; both apply
to text queries (file queries skip the reranker).

| Param              | What it filters       | Range          | Recommended for "only relevant" |
|--------------------|-----------------------|----------------|---------------------------------|
| `min_similarity`   | per-space cosine sim  | `0.0` – `1.0`  | `0.6` – `0.7`                   |
| `min_rerank_score` | cross-encoder logit   | `-15` – `+10`  | `-5` (drops off-topic / nonsense, keeps paraphrase) |

`min_rerank_score` is the cleaner cutoff. Calibration on an internal eval set
(`scripts/eval.py`): lexical exact ≈ +5, legitimate paraphrase ≈ -3 to -4,
off-topic / nonsense ≈ -10. Default is -5 — drops junk while keeping
paraphrase. Each `/api/retrieve` result includes a `rerank_score` so callers
can pick their own threshold post-hoc.

### Retrieval quality (`scripts/eval.py`)

Run an end-to-end retrieval evaluation against your live backend:

```bash
python scripts/eval.py
```

Builds a small gold-labeled corpus, fires hard queries (paraphrase, distractor,
multi-hop, rare-entity, out-of-domain), reports Hit@5, MRR, P@5, and out-of-domain
rejection rate. Use it to tune thresholds before changing prod config.

## Stack

- **Backend**: FastAPI + ChromaDB + SQLite (vault metadata) + BM25 + cross-encoder reranker
- **Frontend**: React + vanilla CSS
- **Encoders**: Meta Perception Encoder — `PE-Core-L14-336` (text/image) + `facebook/pe-av-large` (audio/video)
- **Reranker**: `BAAI/bge-reranker-v2-m3`
- **Dimensions**: 1024 (fixed, all modalities project to a shared space)
- **Retrieval**: dense × 3 PE spaces + BM25 → RRF → cross-encoder rerank → MMR → top-K

## Operations

**Backups.** State lives in two places — `chroma_db/` (vectors) and `embed.db`
(metadata). Snapshot both with:

```bash
./scripts/backup.sh                # → ./backups/embed-<timestamp>.tgz
./scripts/backup.sh /mnt/snapshots # custom destination
```

Old snapshots in the destination dir are pruned after `BACKUP_RETENTION_DAYS`
(default 30). Restore by stopping the server, replacing the two paths from the
tarball, and restarting.

**Orphan upload sweep.** Files left in `uploads/` after a crashed embed are
swept on startup. Trigger manually with admin auth:

```bash
curl -X POST -H "X-API-Key: $ADMIN_API_KEY" \
     "http://localhost:8000/api/admin/orphans/<vault>?dry_run=true"
```

**Structured logs.** `LOG_FORMAT=json` emits JSON-per-line for log shippers.

## License

MIT
