"""One-process SQLite store with atomic writes and JSON documents at the API boundary."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from .scanner import read_text_tree
from .seed import demo_records
from .util import utcnow


SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1), data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY, content TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, severity TEXT NOT NULL, state TEXT NOT NULL,
    created_at TEXT NOT NULL, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS signals_filter ON signals(kind, severity, state);
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY, state TEXT NOT NULL, cve TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS remediations (
    id TEXT PRIMARY KEY, signal_id TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS remediation_signal ON remediations(signal_id);
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY, status TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pull_requests (
    id TEXT PRIMARY KEY, number INTEGER NOT NULL, state TEXT NOT NULL, updated_at TEXT NOT NULL, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS pull_requests_updated ON pull_requests(state, updated_at);
CREATE TABLE IF NOT EXISTS release_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, kind TEXT NOT NULL,
    pr_id TEXT, occurred_at TEXT NOT NULL, received_at TEXT NOT NULL, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS release_events_cursor ON release_events(seq);
CREATE TABLE IF NOT EXISTS release_decisions (
    id TEXT PRIMARY KEY, pr_id TEXT NOT NULL, head_sha TEXT NOT NULL,
    decision TEXT NOT NULL, evidence_hash TEXT NOT NULL, created_at TEXT NOT NULL, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS release_decision_pr ON release_decisions(pr_id, created_at);
CREATE TABLE IF NOT EXISTS activity (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY, fetched_at REAL NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class Database:
    def __init__(self, path: str, example_dir: Path | None = None):
        self.example_dir = example_dir
        if path != ":memory:":
            Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, timeout=10, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(SCHEMA)
            if not self._db.execute("SELECT 1 FROM workspace").fetchone():
                self._seed_demo()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    @staticmethod
    def _load(row: sqlite3.Row | None) -> dict | None:
        return json.loads(row["data"]) if row else None

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set_meta(self, key: str, value: Any) -> None:
        with self.transaction() as db:
            db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    def increment_meta(self, key: str) -> int:
        with self.transaction() as db:
            row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            value = (json.loads(row["value"]) if row else 0) + 1
            db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))
        return value

    def workspace(self) -> dict:
        with self._lock:
            return self._load(self._db.execute("SELECT data FROM workspace WHERE singleton=1").fetchone()) or {}

    def files(self) -> dict:
        """Preserve legacy plain-text seeds and JSON-encode structured repository records."""
        with self._lock:
            rows = self._db.execute("SELECT path,content FROM files ORDER BY path").fetchall()
        result = {}
        for row in rows:
            if row["content"].startswith('{"__driftci_file_v1__":'):
                record = json.loads(row["content"])["__driftci_file_v1__"]
                result[row["path"]] = {"path": row["path"], **record}
            else:
                result[row["path"]] = row["content"]
        return result

    def replace_workspace(self, workspace: dict, files: dict[str, str], clear_operational: bool = True) -> None:
        with self.transaction() as db:
            db.execute("INSERT INTO workspace(singleton,data) VALUES(1,?) ON CONFLICT(singleton) DO UPDATE SET data=excluded.data", (json.dumps(workspace),))
            db.execute("DELETE FROM files")
            db.executemany("INSERT INTO files(path,content) VALUES(?,?)", [(path, json.dumps({"__driftci_file_v1__": {"path": path, **value}}) if isinstance(value, dict) else value) for path, value in sorted(files.items())])
            if clear_operational:
                for table in ("signals", "incidents", "remediations", "sources", "activity", "pull_requests", "release_events", "release_decisions"):
                    db.execute(f"DELETE FROM {table}")
            db.execute("INSERT INTO meta(key,value) VALUES('last_scan_at','null') ON CONFLICT(key) DO UPDATE SET value='null'")
            db.execute("DELETE FROM meta WHERE key='vulnerability_baseline_at'")

    def reset_demo(self) -> None:
        with self.transaction() as db:
            for table in ("signals", "incidents", "remediations", "sources", "activity", "pull_requests", "release_events", "release_decisions"):
                db.execute(f"DELETE FROM {table}")
            db.execute("INSERT INTO meta(key,value) VALUES('last_scan_at','null') ON CONFLICT(key) DO UPDATE SET value='null'")
            db.execute("DELETE FROM meta WHERE key='vulnerability_baseline_at'")
            self._seed_demo(db)

    def _seed_demo(self, db: sqlite3.Connection | None = None) -> None:
        files = read_text_tree(self.example_dir) if self.example_dir else {}
        records = demo_records(files or None)
        if db is None:
            with self.transaction() as transaction:
                self._write_demo(transaction, records)
        else:
            self._write_demo(db, records)

    @staticmethod
    def _write_demo(db: sqlite3.Connection, records: dict) -> None:
        db.execute("INSERT INTO workspace(singleton,data) VALUES(1,?) ON CONFLICT(singleton) DO UPDATE SET data=excluded.data", (json.dumps(records["workspace"]),))
        db.execute("DELETE FROM files")
        db.executemany("INSERT INTO files(path,content) VALUES(?,?)", sorted(records["files"].items()))
        for row in records["signals"]:
            Database._insert_document(db, "signals", row)
        for row in records["incidents"]:
            Database._insert_document(db, "incidents", row)
        for row in records["sources"]:
            Database._insert_document(db, "sources", row)
        for row in records["activity"]:
            Database._insert_document(db, "activity", row)

    @staticmethod
    def _insert_document(db: sqlite3.Connection, table: str, data: dict) -> None:
        encoded = json.dumps(data, ensure_ascii=False)
        if table == "signals":
            db.execute("INSERT OR REPLACE INTO signals(id,kind,severity,state,created_at,data) VALUES(?,?,?,?,?,?)", (data["id"], data["kind"], data["severity"], data["state"], data["created_at"], encoded))
        elif table == "incidents":
            db.execute("INSERT OR REPLACE INTO incidents(id,state,cve,data) VALUES(?,?,?,?)", (data["id"], data["state"], data["cve"], encoded))
        elif table == "sources":
            db.execute("INSERT OR REPLACE INTO sources(id,status,data) VALUES(?,?,?)", (data["id"], data["status"], encoded))
        elif table == "activity":
            db.execute("INSERT OR REPLACE INTO activity(id,created_at,data) VALUES(?,?,?)", (data["id"], data["created_at"], encoded))

    def get_signal(self, ident: str) -> dict | None:
        with self._lock:
            return self._load(self._db.execute("SELECT data FROM signals WHERE id=?", (ident,)).fetchone())

    def list_signals(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM signals").fetchall()
        return [json.loads(row["data"]) for row in rows]

    def save_signal(self, data: dict) -> None:
        with self.transaction() as db:
            self._insert_document(db, "signals", data)

    def delete_signal(self, ident: str) -> None:
        with self.transaction() as db:
            db.execute("DELETE FROM signals WHERE id=?", (ident,))

    def get_incident(self, ident: str) -> dict | None:
        with self._lock:
            return self._load(self._db.execute("SELECT data FROM incidents WHERE id=?", (ident,)).fetchone())

    def list_incidents(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM incidents").fetchall()
        return [json.loads(row["data"]) for row in rows]

    def save_incident(self, data: dict) -> None:
        with self.transaction() as db:
            self._insert_document(db, "incidents", data)

    def delete_incident(self, ident: str) -> None:
        with self.transaction() as db:
            db.execute("DELETE FROM incidents WHERE id=?", (ident,))

    def get_remediation(self, ident: str) -> dict | None:
        with self._lock:
            return self._load(self._db.execute("SELECT data FROM remediations WHERE id=?", (ident,)).fetchone())

    def for_signal(self, ident: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM remediations WHERE signal_id=?", (ident,)).fetchall()
        return [json.loads(row["data"]) for row in rows]

    def list_remediations(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM remediations ORDER BY created_at DESC").fetchall()
        return [json.loads(row["data"]) for row in rows]

    def save_remediation(self, data: dict) -> None:
        with self.transaction() as db:
            db.execute("INSERT OR REPLACE INTO remediations(id,signal_id,status,created_at,data) VALUES(?,?,?,?,?)", (data["id"], data["signal_id"], data["status"], data["created_at"], json.dumps(data, ensure_ascii=False)))

    def delete_remediations_for_signal(self, ident: str) -> None:
        with self.transaction() as db:
            db.execute("DELETE FROM remediations WHERE signal_id=?", (ident,))

    def list_sources(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM sources").fetchall()
        return [json.loads(row["data"]) for row in rows]

    def get_source(self, ident: str) -> dict | None:
        with self._lock:
            return self._load(self._db.execute("SELECT data FROM sources WHERE id=?", (ident,)).fetchone())

    def save_source(self, data: dict) -> None:
        with self.transaction() as db:
            previous = self._load(db.execute("SELECT data FROM sources WHERE id=?", (data["id"],)).fetchone()) or {}
            previous.update(deepcopy(data))
            self._insert_document(db, "sources", previous)

    def delete_source(self, ident: str) -> None:
        with self.transaction() as db:
            db.execute("DELETE FROM sources WHERE id=?", (ident,))

    def get_pull_request(self, ident: str) -> dict | None:
        with self._lock:
            return self._load(self._db.execute("SELECT data FROM pull_requests WHERE id=?", (ident,)).fetchone())

    def list_pull_requests(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM pull_requests").fetchall()
        return [json.loads(row["data"]) for row in rows]

    @staticmethod
    def _insert_release_event(db: sqlite3.Connection, data: dict) -> dict | None:
        cursor = db.execute(
            "INSERT OR IGNORE INTO release_events(id,kind,pr_id,occurred_at,received_at,data) VALUES(?,?,?,?,?,?)",
            (data["id"], data["kind"], data.get("pr_id"), data["occurred_at"], data["received_at"], json.dumps(data, ensure_ascii=False)),
        )
        if not cursor.rowcount:
            return None
        row = dict(data, seq=cursor.lastrowid)
        db.execute("UPDATE release_events SET data=? WHERE seq=?", (json.dumps(row, ensure_ascii=False), cursor.lastrowid))
        return row

    def save_pull_request(self, data: dict, events: list[dict] | None = None) -> list[dict]:
        with self.transaction() as db:
            db.execute(
                "INSERT INTO pull_requests(id,number,state,updated_at,data) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,updated_at=excluded.updated_at,data=excluded.data",
                (data["id"], data["number"], data["state"], data["updated_at"], json.dumps(data, ensure_ascii=False)),
            )
            return [event for item in events or [] if (event := self._insert_release_event(db, item)) is not None]

    def add_release_event(self, data: dict) -> dict | None:
        with self.transaction() as db:
            return self._insert_release_event(db, data)

    def list_release_events(self, after: int = 0, pr_id: str | None = None, limit: int = 100) -> list[dict]:
        limit = min(500, max(1, limit))
        with self._lock:
            if after:
                rows = self._db.execute("SELECT data FROM release_events WHERE seq>? AND (? IS NULL OR pr_id=?) ORDER BY seq LIMIT ?", (after, pr_id, pr_id, limit)).fetchall()
            else:
                rows = self._db.execute("SELECT data FROM release_events WHERE (? IS NULL OR pr_id=?) ORDER BY seq DESC LIMIT ?", (pr_id, pr_id, limit)).fetchall()[::-1]
        return [json.loads(row["data"]) for row in rows]

    def has_release_event(self, ident: str) -> bool:
        with self._lock:
            return self._db.execute("SELECT 1 FROM release_events WHERE id=?", (ident,)).fetchone() is not None

    def latest_release_event_seq(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT COALESCE(MAX(seq), 0) AS seq FROM release_events").fetchone()
        return row["seq"]

    def release_decision(self, pr_id: str) -> dict | None:
        with self._lock:
            return self._load(self._db.execute("SELECT data FROM release_decisions WHERE pr_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1", (pr_id,)).fetchone())

    def save_release_decision(self, data: dict) -> None:
        with self.transaction() as db:
            db.execute("INSERT INTO release_decisions(id,pr_id,head_sha,decision,evidence_hash,created_at,data) VALUES(?,?,?,?,?,?,?)", (
                data["id"], data["pr_id"], data["head_sha"], data["decision"], data["evidence_hash"], data["created_at"], json.dumps(data, ensure_ascii=False),
            ))

    def add_activity(self, kind: str, title: str, detail: str, created_at: str | None = None) -> dict:
        timestamp = created_at or utcnow()
        data = {"id": f"a-{timestamp}-{threading.get_ident()}", "type": kind, "title": title, "detail": detail, "created_at": timestamp}
        # The timestamp plus SQLite rowid makes display order deterministic for same-second events.
        with self.transaction() as db:
            rows = db.execute("SELECT COUNT(*) AS n FROM activity").fetchone()
            data["id"] = f"a-{timestamp}-{rows['n']}"
            self._insert_document(db, "activity", data)
        return data

    def list_activity(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM activity ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row["data"]) for row in rows]

    def cache_get(self, key: str) -> dict | None:
        with self._lock:
            return self._load(self._db.execute("SELECT data FROM cache WHERE key=?", (key,)).fetchone())

    def cache_set(self, key: str, fetched_at: float, data: dict) -> None:
        with self.transaction() as db:
            db.execute("INSERT INTO cache(key,fetched_at,data) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET fetched_at=excluded.fetched_at,data=excluded.data", (key, fetched_at, json.dumps(data, ensure_ascii=False)))

    def cache_fetched_at(self, key: str) -> float:
        with self._lock:
            row = self._db.execute("SELECT fetched_at FROM cache WHERE key=?", (key,)).fetchone()
        return row["fetched_at"] if row else 0
