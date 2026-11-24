"""Local history for assets imported into the desktop workspace."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import sqlite3

import numpy as np

from app.config import DATA_DIR

logger = logging.getLogger(__name__)


def signal_fingerprint(audio: np.ndarray, sample_rate: int) -> tuple:
    """Compare PCM, layout and rate without retaining a second signal."""
    pcm = np.ascontiguousarray(audio, dtype=np.float32)
    return sample_rate, pcm.shape, hashlib.sha256(pcm).digest()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "workspace-history.sqlite3"
    os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
    connection = sqlite3.connect(path)
    try:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS workspace_sources (
                file_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS workspace_sources_digest
                ON workspace_sources (source_sha256);
            CREATE TABLE IF NOT EXISTS workspace_events (
                event_id INTEGER PRIMARY KEY,
                file_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                action TEXT NOT NULL,
                revision TEXT,
                details TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS workspace_events_file ON workspace_events (file_id, event_id);
        """)
        return connection
    except Exception:
        connection.close()
        raise


def record_event(file_id: str, action: str, *, revision: str | None = None,
                 source_sha256: str | None = None, **details) -> bool:
    """Append only server-observed facts. A history failure is explicit to logs."""
    try:
        with closing(_connect()) as connection, connection:
            if source_sha256 is not None:
                connection.execute("INSERT INTO workspace_sources VALUES (?, ?)", (file_id, source_sha256))
                details["source_sha256"] = source_sha256
            connection.execute(
                "INSERT INTO workspace_events (file_id, occurred_at, action, revision, details) VALUES (?, ?, ?, ?, ?)",
                (file_id, datetime.now(timezone.utc).isoformat(), action, revision, json.dumps(details)),
            )
        return True
    except (OSError, sqlite3.Error):
        logger.warning("Workspace history could not record %s", action, exc_info=True)
        return False


def read_history(file_id: str, *, before: int | None = None, limit: int = 50) -> dict:
    """Include prior imports of the exact same source bytes, never a filename match."""
    with closing(_connect()) as connection:
        rows = connection.execute("""
            SELECT event_id, occurred_at, action, revision, details
            FROM workspace_events
            WHERE (
                file_id = ? OR file_id IN (
                    SELECT file_id FROM workspace_sources
                    WHERE source_sha256 = (SELECT source_sha256 FROM workspace_sources WHERE file_id = ?)
                )
            ) AND (? IS NULL OR event_id < ?)
            ORDER BY event_id DESC LIMIT ?
        """, (file_id, file_id, before, before, limit + 1)).fetchall()
    return {
        "events": [
            {
                "id": event_id, "occurred_at": occurred_at, "action": action,
                "revision": revision, "details": json.loads(details),
            }
            for event_id, occurred_at, action, revision, details in rows[:limit]
        ],
        "next_before": rows[limit - 1][0] if len(rows) > limit else None,
    }
