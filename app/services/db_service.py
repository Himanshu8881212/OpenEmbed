"""
SQLite metadata layer for vaults and files.

ChromaDB owns the vectors; this module owns the rich metadata:
vault descriptions, per-file lifecycle status, error messages, etc.

Schema:
- vaults: id, name (unique), description, created_at, updated_at
- files:  id, vault_id (FK), filename, mime_type, modality,
          status (queued|embedding|indexed|failed), size_bytes,
          doc_id (chroma doc_id), chunk_count, error_message,
          uploaded_at, indexed_at
"""
from typing import Optional, List, Dict
from datetime import datetime
import sqlite3
import threading
import uuid

from app.core.config import settings
from app.core.logger import app_logger as logger


_VALID_STATUSES = ("queued", "embedding", "indexed", "failed")

_lock = threading.Lock()
_db_path: Optional[str] = None
_ready: bool = False


def _connect() -> sqlite3.Connection:
    """Open a new connection. Caller is responsible for closing it."""
    conn = sqlite3.connect(_db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize() -> bool:
    """Create the SQLite file (if needed) and ensure schema exists."""
    global _db_path, _ready
    try:
        _db_path = settings.sqlite_path
        with _lock:
            conn = _connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS vaults (
                        id          TEXT PRIMARY KEY,
                        name        TEXT NOT NULL UNIQUE,
                        description TEXT NOT NULL DEFAULT '',
                        created_at  TEXT NOT NULL,
                        updated_at  TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS files (
                        id            TEXT PRIMARY KEY,
                        vault_id      TEXT NOT NULL,
                        filename      TEXT NOT NULL,
                        mime_type     TEXT NOT NULL DEFAULT '',
                        modality      TEXT NOT NULL DEFAULT '',
                        status        TEXT NOT NULL DEFAULT 'queued'
                                        CHECK (status IN ('queued','embedding','indexed','failed')),
                        size_bytes    INTEGER NOT NULL DEFAULT 0,
                        doc_id        TEXT NOT NULL DEFAULT '',
                        chunk_count   INTEGER NOT NULL DEFAULT 0,
                        error_message TEXT,
                        uploaded_at   TEXT NOT NULL,
                        indexed_at    TEXT,
                        FOREIGN KEY (vault_id) REFERENCES vaults(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_files_vault   ON files(vault_id);
                    CREATE INDEX IF NOT EXISTS idx_files_doc_id  ON files(doc_id);
                    CREATE INDEX IF NOT EXISTS idx_files_status  ON files(status);
                    """
                )
                conn.commit()
            finally:
                conn.close()
        _ready = True
        logger.info(f"SQLite metadata DB initialized at {_db_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize SQLite: {e}")
        _ready = False
        return False


def is_ready() -> bool:
    return _ready


def backfill_chroma_vaults(vault_names: List[str]) -> int:
    """Insert metadata rows for chroma-only vaults that predate SQLite tracking.
    Returns the count of newly-inserted rows."""
    if not _ready or not vault_names:
        return 0
    now = datetime.utcnow().isoformat()
    inserted = 0
    with _lock:
        conn = _connect()
        try:
            for name in vault_names:
                row = conn.execute("SELECT id FROM vaults WHERE name = ?", (name,)).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO vaults (id, name, description, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), name, "", now, now),
                    )
                    inserted += 1
            conn.commit()
        finally:
            conn.close()
    if inserted:
        logger.info(f"Backfilled {inserted} legacy chroma-only vault(s) into SQLite")
    return inserted


# ── Vault operations ─────────────────────────────────────────────

def _vault_to_dict(row: sqlite3.Row) -> Dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_vault(name: str, description: str = "") -> Dict:
    """Insert a vault row. Raises ValueError if name already exists."""
    now = datetime.utcnow().isoformat()
    vault_id = str(uuid.uuid4())
    with _lock:
        conn = _connect()
        try:
            try:
                conn.execute(
                    "INSERT INTO vaults (id, name, description, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (vault_id, name, description or "", now, now),
                )
                conn.commit()
            except sqlite3.IntegrityError as ie:
                raise ValueError(f"Vault '{name}' already exists") from ie
            row = conn.execute("SELECT * FROM vaults WHERE id = ?", (vault_id,)).fetchone()
        finally:
            conn.close()
    out = _vault_to_dict(row)
    out["file_count"] = 0
    return out


def get_vault(name: str) -> Optional[Dict]:
    """Fetch a vault by name (with file_count)."""
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM vaults WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM files WHERE vault_id = ?", (row["id"],)
        ).fetchone()["c"]
    finally:
        conn.close()
    out = _vault_to_dict(row)
    out["file_count"] = count
    return out


def list_vaults() -> List[Dict]:
    """List all vaults with aggregated file_count."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT v.*, COALESCE(c.file_count, 0) AS file_count
            FROM vaults v
            LEFT JOIN (
                SELECT vault_id, COUNT(*) AS file_count
                FROM files GROUP BY vault_id
            ) c ON c.vault_id = v.id
            ORDER BY v.created_at DESC
            """
        ).fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        d = _vault_to_dict(row)
        d["file_count"] = row["file_count"]
        out.append(d)
    return out


def delete_vault(name: str) -> bool:
    """Delete a vault and (via FK CASCADE) all its files. Returns True if deleted."""
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute("DELETE FROM vaults WHERE name = ?", (name,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


# ── File operations ──────────────────────────────────────────────

def _file_to_dict(row: sqlite3.Row) -> Dict:
    return {
        "id": row["id"],
        "vault_id": row["vault_id"],
        "filename": row["filename"],
        "mime_type": row["mime_type"] or "",
        "modality": row["modality"] or "",
        "status": row["status"],
        "size_bytes": row["size_bytes"],
        "doc_id": row["doc_id"] or "",
        "chunk_count": row["chunk_count"],
        "error_message": row["error_message"],
        "uploaded_at": row["uploaded_at"],
        "indexed_at": row["indexed_at"],
    }


def record_file(
    vault_name: str,
    filename: str,
    mime_type: str,
    modality: str,
    doc_id: str,
    size_bytes: int,
    status: str = "queued",
) -> Dict:
    """
    Insert a file row, creating the vault metadata row on the fly if it
    doesn't already exist (keeps existing chroma-only stores in sync).
    """
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'")

    now = datetime.utcnow().isoformat()
    file_id = str(uuid.uuid4())

    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT id FROM vaults WHERE name = ?", (vault_name,)
            ).fetchone()
            if row is None:
                # Backfill: chroma-only vault gets a metadata row.
                vault_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO vaults (id, name, description, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (vault_id, vault_name, "", now, now),
                )
            else:
                vault_id = row["id"]

            conn.execute(
                "INSERT INTO files (id, vault_id, filename, mime_type, modality, status, "
                "size_bytes, doc_id, chunk_count, error_message, uploaded_at, indexed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, NULL)",
                (
                    file_id, vault_id, filename, mime_type or "", modality or "",
                    status, int(size_bytes or 0), doc_id or "", now,
                ),
            )
            conn.commit()
            new_row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        finally:
            conn.close()
    return _file_to_dict(new_row)


def update_file_status(
    file_id: str,
    status: str,
    chunk_count: Optional[int] = None,
    error: Optional[str] = None,
) -> bool:
    """Update lifecycle fields for a file. Returns True if a row was updated."""
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'")

    indexed_at = datetime.utcnow().isoformat() if status == "indexed" else None

    fields = ["status = ?"]
    args: List = [status]

    if chunk_count is not None:
        fields.append("chunk_count = ?")
        args.append(int(chunk_count))
    if error is not None:
        fields.append("error_message = ?")
        args.append(error)
    if indexed_at is not None:
        fields.append("indexed_at = ?")
        args.append(indexed_at)

    args.append(file_id)
    sql = f"UPDATE files SET {', '.join(fields)} WHERE id = ?"

    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(sql, args)
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def list_files(vault_name: str, status: Optional[str] = None) -> List[Dict]:
    """List files in a vault, optionally filtered by status."""
    if status is not None and status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status filter '{status}'")

    conn = _connect()
    try:
        vault = conn.execute(
            "SELECT id FROM vaults WHERE name = ?", (vault_name,)
        ).fetchone()
        if vault is None:
            return []
        if status:
            rows = conn.execute(
                "SELECT * FROM files WHERE vault_id = ? AND status = ? "
                "ORDER BY uploaded_at DESC",
                (vault["id"], status),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM files WHERE vault_id = ? ORDER BY uploaded_at DESC",
                (vault["id"],),
            ).fetchall()
    finally:
        conn.close()
    return [_file_to_dict(r) for r in rows]


def get_file(file_id: str) -> Optional[Dict]:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    finally:
        conn.close()
    return _file_to_dict(row) if row else None
