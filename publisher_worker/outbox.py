"""Journal SQLite privado por empresa; ninguna fase mutante se repite."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from webapp.publications.contracts import canonical_hash

QUARANTINED = "quarantined_before_dispatch"


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
                CREATE TABLE IF NOT EXISTS pre_dispatch_manifests (
                    attempt TEXT PRIMARY KEY REFERENCES attempts(attempt),
                    manifest TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS pre_dispatch_acknowledgements (
                    attempt TEXT PRIMARY KEY REFERENCES pre_dispatch_manifests(attempt),
                    receipt TEXT NOT NULL, receipt_sha256 TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS quarantine_stage_immutable BEFORE UPDATE OF stage ON attempts
                    WHEN OLD.stage='quarantined_before_dispatch' AND NEW.stage<>OLD.stage
                    BEGIN SELECT RAISE(ABORT,'quarantined_attempt'); END;
                CREATE TRIGGER IF NOT EXISTS quarantine_phase_blocked BEFORE INSERT ON phases
                    WHEN EXISTS(SELECT 1 FROM attempts WHERE attempt=NEW.attempt AND stage='quarantined_before_dispatch')
                    BEGIN SELECT RAISE(ABORT,'quarantined_attempt'); END;
                CREATE TRIGGER IF NOT EXISTS quarantine_ticket_blocked BEFORE INSERT ON tickets
                    WHEN EXISTS(SELECT 1 FROM attempts WHERE attempt=NEW.attempt AND stage='quarantined_before_dispatch')
                    BEGIN SELECT RAISE(ABORT,'quarantined_attempt'); END;
                CREATE TRIGGER IF NOT EXISTS quarantine_requires_ack BEFORE UPDATE OF done ON attempts
                    WHEN OLD.stage='quarantined_before_dispatch' AND NEW.done=1
                    AND NOT EXISTS(SELECT 1 FROM pre_dispatch_acknowledgements WHERE attempt=OLD.attempt)
                    BEGIN SELECT RAISE(ABORT,'terminal_ack_required'); END;
            """)
            for table in ("pre_dispatch_manifests", "pre_dispatch_acknowledgements"):
                for operation in ("UPDATE", "DELETE"):
                    con.execute(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_{operation.lower()}_immutable BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable_pre_dispatch'); END"
                    )
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
        if new == QUARANTINED:
            raise ValueError("quarantine_helper_required")
        with self.connect() as con:
            return (
                con.execute(
                    "UPDATE attempts SET stage=? WHERE attempt=? AND stage=? AND stage<>'quarantined_before_dispatch'",
                    (new, attempt, expected),
                ).rowcount
                == 1
            )

    def active(self) -> list[dict]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT attempt,claim,snapshot,stage,pending,result FROM attempts WHERE done=0 AND stage<>'quarantined_before_dispatch' ORDER BY rowid"
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
                "UPDATE attempts SET pending=?,result=? WHERE attempt=? AND stage<>'quarantined_before_dispatch'",
                (encoded(body), encoded(result), attempt),
            )
        return body

    def reported(self, attempt: str, terminal: bool) -> None:
        with self.connect() as con:
            con.execute(
                "UPDATE attempts SET pending=NULL,done=? WHERE attempt=? AND stage<>'quarantined_before_dispatch'",
                (int(terminal), attempt),
            )

    def finish_local(self, attempt: str) -> None:
        with self.connect() as con:
            con.execute(
                "UPDATE attempts SET done=1 WHERE attempt=? AND stage<>'quarantined_before_dispatch'",
                (attempt,),
            )

    def _pre_dispatch_binding(self, con, claim, contract_hash, media_sha256):
        row = con.execute(
            "SELECT claim,snapshot,stage,done FROM attempts WHERE attempt=?",
            (claim.get("attempt_id"),),
        ).fetchone()
        if row is None or json.loads(row[0]) != claim:
            raise ValueError("pre_dispatch_claim_mismatch")
        snapshot = json.loads(row[1])
        if (
            snapshot.get("tenant_id") != self.tenant_id
            or snapshot.get("connection", {}).get("tenant_id") != self.tenant_id
            or snapshot.get("connection", {}).get("platform") != "instagram"
            or snapshot.get("media", {}).get("kind") != "gallery_image"
            or snapshot.get("media", {}).get("mime") != "image/jpeg"
            or not snapshot.get("destination", "").startswith("instagram:")
            or canonical_hash(snapshot) != contract_hash
            or claim.get("contract_hash") != contract_hash
            or snapshot["media"].get("sha256") != media_sha256
            or not re.fullmatch("[0-9a-f]{64}", media_sha256)
        ):
            raise ValueError("pre_dispatch_binding_mismatch")
        return row, snapshot

    def quarantine_before_dispatch(self, claim, *, contract_hash, media_sha256, now):
        """Original worker exclusion plus durable CAS; a hash is integrity, not proof."""
        with self.exclusive() as acquired:
            if not acquired:
                raise ValueError("outbox_worker_active")
            with self.connect() as con:
                con.execute("BEGIN IMMEDIATE")
                row, _ = self._pre_dispatch_binding(con, claim, contract_hash, media_sha256)
                attempt = claim["attempt_id"]
                phases = con.execute(
                    "SELECT COUNT(*) FROM phases WHERE attempt=?", (attempt,)
                ).fetchone()[0]
                tickets = con.execute(
                    "SELECT COUNT(*) FROM tickets WHERE attempt=?", (attempt,)
                ).fetchone()[0]
                if phases or tickets:
                    raise ValueError("pre_dispatch_effect_possible")
                manifest = {
                    "schema_version": 1,
                    "tenant_id": self.tenant_id,
                    "attempt_id": attempt,
                    "claim_id": claim["claim_id"],
                    "delivery_id": claim["delivery_id"],
                    "contract_hash": contract_hash,
                    "media_sha256": media_sha256,
                    "claim_sha256": canonical_hash(claim),
                    "platform": "instagram",
                    "media_mime": "image/jpeg",
                    "local_stage": QUARANTINED,
                    "phase_count": 0,
                    "local_ticket_count": 0,
                    "started_confirmed": True,
                    "done": False,
                }
                digest = canonical_hash(manifest)
                old = con.execute(
                    "SELECT manifest,manifest_sha256 FROM pre_dispatch_manifests WHERE attempt=?",
                    (attempt,),
                ).fetchone()
                if old:
                    if row[2] != QUARANTINED or old != (encoded(manifest), digest):
                        raise ValueError("pre_dispatch_manifest_conflict")
                    return {"manifest": json.loads(old[0]), "manifest_sha256": old[1]}
                if row[2:] != ("start_confirmed", 0):
                    raise ValueError("pre_dispatch_not_start_confirmed")
                if (
                    con.execute(
                        "UPDATE attempts SET stage=? WHERE attempt=? AND stage='start_confirmed' AND done=0",
                        (QUARANTINED, attempt),
                    ).rowcount
                    != 1
                ):
                    raise ValueError("pre_dispatch_cas_failed")
                con.execute(
                    "INSERT INTO pre_dispatch_manifests VALUES (?,?,?,?)",
                    (attempt, encoded(manifest), digest, now),
                )
                return {"manifest": manifest, "manifest_sha256": digest}

    def complete_pre_dispatch(self, claim, status):
        """Only an authenticated original-worker GET acknowledgement makes done=1."""
        with self.exclusive() as acquired:
            if not acquired:
                raise ValueError("outbox_worker_active")
            with self.connect() as con:
                con.execute("BEGIN IMMEDIATE")
                old = con.execute(
                    "SELECT manifest_sha256 FROM pre_dispatch_manifests WHERE attempt=?",
                    (claim["attempt_id"],),
                ).fetchone()
                if old is None:
                    raise ValueError("pre_dispatch_manifest_required")
                row, snapshot = self._pre_dispatch_binding(
                    con,
                    claim,
                    claim["contract_hash"],
                    status.get("snapshot", {}).get("media", {}).get("sha256", ""),
                )
                expected = {
                    "state": "failed",
                    "remote_id": None,
                    "permalink": None,
                    "evidence": {"error_code": "failed_before_dispatch"},
                }
                if (
                    row[2] != QUARANTINED
                    or status.get("state") != "failed"
                    or status.get("attempt_id") != claim["attempt_id"]
                    or status.get("post_permitted") is not False
                    or status.get("contract_hash") != claim["contract_hash"]
                    or status.get("snapshot") != snapshot
                    or status.get("result") != expected
                ):
                    raise ValueError("pre_dispatch_terminal_ack_invalid")
                receipt = {
                    "attempt_id": claim["attempt_id"],
                    "claim_id": claim["claim_id"],
                    "manifest_sha256": old[0],
                    "result_hash": canonical_hash(expected),
                    "state": "failed",
                    "post_permitted": False,
                }
                previous = con.execute(
                    "SELECT receipt,receipt_sha256 FROM pre_dispatch_acknowledgements WHERE attempt=?",
                    (claim["attempt_id"],),
                ).fetchone()
                if previous and previous != (encoded(receipt), canonical_hash(receipt)):
                    raise ValueError("pre_dispatch_terminal_ack_conflict")
                if not previous:
                    con.execute(
                        "INSERT INTO pre_dispatch_acknowledgements VALUES (?,?,?)",
                        (claim["attempt_id"], encoded(receipt), canonical_hash(receipt)),
                    )
                con.execute(
                    "UPDATE attempts SET done=1 WHERE attempt=? AND stage=?",
                    (claim["attempt_id"], QUARANTINED),
                )

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
            con.execute("BEGIN IMMEDIATE")
            return (
                con.execute(
                    "INSERT OR IGNORE INTO phases(attempt,phase) SELECT ?,? WHERE EXISTS (SELECT 1 FROM attempts WHERE attempt=? AND stage<>'quarantined_before_dispatch' AND done=0)",
                    (self.attempt, phase, self.attempt),
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
