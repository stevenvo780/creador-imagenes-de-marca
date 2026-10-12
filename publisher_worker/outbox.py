"""Journal SQLite privado por empresa; ninguna fase mutante se repite."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def encoded(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Outbox:
    def __init__(self, path: Path | str, *, tenant_id: int):
        if type(tenant_id) is not int or tenant_id <= 0:
            raise ValueError("invalid_tenant")
        self.path, self.tenant_id = Path(path), tenant_id
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        os.chmod(self.path, 0o600)
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS identity (tenant INTEGER PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt TEXT PRIMARY KEY, claim TEXT NOT NULL, snapshot TEXT NOT NULL,
                    stage TEXT NOT NULL, pending TEXT, result TEXT, done INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS phases (
                    attempt TEXT NOT NULL REFERENCES attempts(attempt), phase TEXT NOT NULL,
                    receipt TEXT, PRIMARY KEY(attempt, phase));
                CREATE TABLE IF NOT EXISTS tickets (
                    attempt TEXT NOT NULL REFERENCES attempts(attempt), id INTEGER NOT NULL,
                    sha TEXT NOT NULL, expires INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(attempt,id));
            """)
            con.execute("INSERT OR IGNORE INTO identity VALUES (?)", (tenant_id,))
            if con.execute("SELECT tenant FROM identity").fetchall() != [(tenant_id,)]:
                raise ValueError("outbox_tenant_mismatch")

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    @contextmanager
    def exclusive(self):
        fd = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        acquired = False
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                pass
            yield acquired
        finally:
            os.close(fd)

    def reserve(self, claim: dict, snapshot: dict) -> bool:
        if snapshot.get("tenant_id") != self.tenant_id:
            raise ValueError("outbox_tenant_mismatch")
        with self.connect() as con:
            return (
                con.execute(
                    "INSERT OR IGNORE INTO attempts(attempt,claim,snapshot,stage) VALUES (?,?,?,'reserved')",
                    (claim["attempt_id"], encoded(claim), encoded(snapshot)),
                ).rowcount
                == 1
            )

    def stage(self, attempt: str, expected: str, new: str) -> bool:
        with self.connect() as con:
            return (
                con.execute(
                    "UPDATE attempts SET stage=? WHERE attempt=? AND stage=?",
                    (new, attempt, expected),
                ).rowcount
                == 1
            )

    def active(self) -> list[dict]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT attempt,claim,snapshot,stage,pending,result FROM attempts WHERE done=0 ORDER BY rowid"
            ).fetchall()
        return [
            dict(
                attempt_id=a,
                claim=json.loads(c),
                snapshot=json.loads(s),
                stage=g,
                pending=json.loads(p) if p else None,
                result=json.loads(r) if r else None,
            )
            for a, c, s, g, p, r in rows
        ]

    def queue_report(self, attempt: str, result: dict, confirmation: dict | None = None) -> dict:
        body: dict = {"result": result, "confirmation": confirmation}
        body["event_key"] = "worker:" + hashlib.sha256(encoded(body).encode()).hexdigest()
        with self.connect() as con:
            con.execute(
                "UPDATE attempts SET pending=?,result=? WHERE attempt=?",
                (encoded(body), encoded(result), attempt),
            )
        return body

    def reported(self, attempt: str, terminal: bool) -> None:
        with self.connect() as con:
            con.execute(
                "UPDATE attempts SET pending=NULL,done=? WHERE attempt=?", (int(terminal), attempt)
            )

    def finish_local(self, attempt: str) -> None:
        with self.connect() as con:
            con.execute("UPDATE attempts SET done=1 WHERE attempt=?", (attempt,))

    def journal(self, attempt: str) -> PhaseJournal:
        return PhaseJournal(self, attempt)

    def record_ticket(self, attempt: str, ticket: dict) -> None:
        # No conservar URL bearer de entrega; sólo su alcance y vencimiento.
        with self.connect() as con:
            con.execute(
                "INSERT INTO tickets(attempt,id,sha,expires) VALUES (?,?,?,?)",
                (attempt, ticket["id"], ticket["media_sha256"], ticket["expires_at"]),
            )

    def tickets(self) -> list[tuple]:
        with self.connect() as con:
            return con.execute("SELECT attempt,id,expires FROM tickets WHERE revoked=0").fetchall()

    def revoked(self, attempt: str, ticket_id: int) -> None:
        with self.connect() as con:
            con.execute(
                "UPDATE tickets SET revoked=1 WHERE attempt=? AND id=?", (attempt, ticket_id)
            )


class PhaseJournal:
    """Binding constructor; sólo IDs/recibos seleccionados, nunca token/URL/raw JSON."""

    ALLOWED = frozenset({"id", "remote_id", "receipt_sha256", "status", "scope"})

    def __init__(self, box: Outbox, attempt: str):
        self.box, self.attempt = box, attempt

    def begin(self, phase: str) -> bool:
        with self.box.connect() as con:
            return (
                con.execute(
                    "INSERT OR IGNORE INTO phases(attempt,phase) VALUES (?,?)",
                    (self.attempt, phase),
                ).rowcount
                == 1
            )

    def complete(self, phase: str, receipt: dict) -> None:
        if set(receipt) - self.ALLOWED or any(
            not isinstance(v, str) or len(v) > 256 for v in receipt.values()
        ):
            raise ValueError("invalid_private_receipt")
        with self.box.connect() as con:
            if (
                con.execute(
                    "UPDATE phases SET receipt=? WHERE attempt=? AND phase=? AND receipt IS NULL",
                    (encoded(receipt), self.attempt, phase),
                ).rowcount
                != 1
            ):
                raise ValueError("phase_already_completed")

    def read(self, phase: str) -> dict | None:
        with self.box.connect() as con:
            row = con.execute(
                "SELECT receipt FROM phases WHERE attempt=? AND phase=?", (self.attempt, phase)
            ).fetchone()
        return json.loads(row[0]) if row and row[0] else None
