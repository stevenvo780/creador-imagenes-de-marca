"""Explicit original-worker quarantine/attestation and authenticated ACK sync.

Run manually with a private worker grant. This helper never resolves provider
credentials, creates delivery tickets, dispatches media, or calls owner routes.
The owner separately qualifies historical code/configuration/outbox/exclusion.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import time
from pathlib import Path

from webapp.publications.contracts import PublicationError

from .client import WorkerAPIError, WorkerClient
from .outbox import Outbox


def read_private_worker_grant(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or not 0 < info.st_size <= 16384
            or stat.S_IMODE(info.st_mode) not in (0o600, 0o640)
            or info.st_uid not in (0, os.geteuid())
        ):
            raise ValueError("private_worker_grant_required")
        value = os.read(descriptor, 16385).decode("ascii")
        if (
            len(value) <= len("eikon_pub_worker_")
            or len(value) != info.st_size
            or not value.startswith("eikon_pub_worker_")
            or any(c.isspace() or c == "\x00" for c in value)
        ):
            raise ValueError("private_worker_grant_required")
        return value
    finally:
        os.close(descriptor)


def original_claim(box: Outbox, attempt_id: str, contract_hash: str, media_sha256: str) -> dict:
    with box.connect() as con:
        found = con.execute("SELECT claim FROM attempts WHERE attempt=?", (attempt_id,)).fetchone()
        if found is None:
            raise ValueError("original_attempt_required")
        claim = json.loads(found[0])
        box._pre_dispatch_binding(con, claim, contract_hash, media_sha256)
        return claim


def attest(
    box: Outbox,
    client: WorkerClient,
    claim: dict,
    *,
    contract_hash: str,
    media_sha256: str,
    now: int,
) -> dict:
    if client.tenant_id != box.tenant_id:
        raise ValueError("pre_dispatch_tenant_mismatch")
    sealed = box.quarantine_before_dispatch(
        claim, contract_hash=contract_hash, media_sha256=media_sha256, now=now
    )
    response = client._request(
        "POST",
        client._attempt_path(claim) + "/pre-dispatch-attestations",
        json={
            **sealed,
            "event_key": "original:" + sealed["manifest_sha256"],
        },
    )
    fields = {
        "attestation_id",
        "attempt_id",
        "tenant_id",
        "manifest_sha256",
        "worker_grant_id",
        "post_permitted",
        "state",
        "attested_at",
    }
    if (
        not isinstance(response, dict)
        or set(response) != fields
        or response["attempt_id"] != claim["attempt_id"]
        or response["tenant_id"] != box.tenant_id
        or response["manifest_sha256"] != sealed["manifest_sha256"]
        or response["post_permitted"] is not False
        or response["state"] != "attested_before_dispatch"
        or any(
            type(response[key]) is not int or response[key] <= 0
            for key in ("attestation_id", "worker_grant_id", "attested_at")
        )
    ):
        raise ValueError("pre_dispatch_attestation_ack_invalid")
    return response


def sync_terminal_ack(box: Outbox, client: WorkerClient, claim: dict) -> dict:
    if client.tenant_id != box.tenant_id:
        raise ValueError("pre_dispatch_tenant_mismatch")
    status = client.get_claim(claim)
    box.complete_pre_dispatch(claim, status)
    return {
        "state": "failed",
        "reason": "failed_before_dispatch",
        "attempt_id": claim["attempt_id"],
        "post_permitted": False,
        "terminal_ack_read": True,
    }


def _existing_outbox(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ValueError("original_private_outbox_required")
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Original-worker pre-dispatch attestation or terminal ACK sync"
    )
    parser.add_argument("action", choices=("attest", "sync-ack"))
    parser.add_argument("--outbox", type=Path, required=True)
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--contract-hash", required=True)
    parser.add_argument("--media-sha256", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    client = None
    try:
        _existing_outbox(args.outbox)
        token = read_private_worker_grant(args.token_file)
        box = Outbox(args.outbox, tenant_id=args.tenant_id)
        claim = original_claim(box, args.attempt_id, args.contract_hash, args.media_sha256)
        client = WorkerClient(args.origin, token, tenant_id=args.tenant_id)
        if args.action == "attest":
            answer = attest(
                box,
                client,
                claim,
                contract_hash=args.contract_hash,
                media_sha256=args.media_sha256,
                now=int(time.time()),
            )
        else:
            answer = sync_terminal_ack(box, client, claim)
        print(json.dumps(answer, sort_keys=True))
        return 0
    except (ValueError, OSError, WorkerAPIError, PublicationError):
        print(json.dumps({"state": "held", "reason": "pre_dispatch_operation_failed"}))
        return 1
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
