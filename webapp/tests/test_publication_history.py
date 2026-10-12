"""Historia real dual: retiro, identidad, corte completo y replay sin autorización."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from webapp import db
from webapp.publications.contracts import Conflict, NotFound
from webapp.tests.test_projects import isolated_db as _isolated_db
from webapp.tests.test_publication_policies import publication_db as _publication_db

isolated_db = _isolated_db
publication_db = _publication_db


def item(delivery=1, destination="facebook:7", state="published", **kwargs):
    return {
        "source_delivery_id": str(delivery),
        "normalized_destination": destination,
        "platform": destination.split(":")[0] if destination else "x",
        "state": state,
        "image_sha256": "a" * 64,
        "receipt": {"remote_id": str(delivery)},
        **kwargs,
    }


def evidence(sources, cut_id="cut-test"):
    return {
        "source_sha256": "b" * 64,
        "receipt_sha256": "c" * 64,
        "cut_manifest": {
            "cut_id": cut_id,
            "scope": "known_inventory",
            "aliases": [],
            "sources": [
                {"source_id": name, "source_sha256": "b" * 64, "items": rows}
                for name, rows in sources.items()
            ],
        },
    }


@pytest.fixture
def history_db(publication_db):
    from webapp.publications.ledger import import_history
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    tenant = owners[0][0]
    with db.connect(url) as con:
        con.execute(
            "UPDATE publication_connections SET remote_id='7' WHERE tenant_id=? AND id=?",
            (tenant, payloads[0]["connection_ids"][0]),
        )
    set_policy(url, *owners[0], 0, payloads[0])
    result = import_history(url, tenant, "legacy-a", [item()], evidence({"legacy-a": [item()]}))
    return url, tenant, result["items"][0]["attempt_id"]


def test_withdrawal_does_not_clear_media_guard(history_db):
    from webapp.publications.ledger import append_event, seen_media

    url, tenant, attempt = history_db
    append_event(url, tenant, attempt, "withdrawn:confirmed", "withdrawn", {"confirmed": True})
    assert seen_media(url, tenant, "facebook:7", "a" * 64)
    with db.connect(url) as con:
        events = con.execute(
            "SELECT kind,payload_json FROM publication_events WHERE tenant_id=? AND attempt_id=? ORDER BY id",
            (tenant, attempt),
        ).fetchall()
    assert [row["kind"] for row in events] == ["published", "withdrawn"]
    assert json.loads(events[0]["payload_json"])["receipt"] == {"remote_id": "1"}


def test_source_delivery_ids_cannot_collide_and_caption_cannot_reset_guard(publication_db):
    from webapp.publications.ledger import import_history, seen_media

    url, owners, _ = publication_db
    tenant = owners[0][0]
    a = import_history(
        url, tenant, "db-a", [item(caption="one")], evidence({"db-a": [item(caption="one")]})
    )
    b = import_history(
        url,
        tenant,
        "db-b",
        [item(caption="two")],
        {"source_sha256": "d" * 64, "receipt_sha256": "e" * 64},
    )
    assert a["items"][0]["id"] != b["items"][0]["id"]
    assert a["items"][0]["attempt_id"] != b["items"][0]["attempt_id"]
    assert seen_media(url, tenant, "facebook:7", "a" * 64)
    assert not seen_media(url, tenant, "facebook:8", "a" * 64)
    assert not seen_media(url, owners[1][0], "facebook:7", "a" * 64)


def test_event_replay_is_idempotent_but_conflicting_payload_is_rejected(history_db):
    from webapp.publications.ledger import append_event

    url, tenant, attempt = history_db
    first = append_event(url, tenant, attempt, "withdrawal", "withdrawn", {"confirmed": True})
    assert (
        append_event(url, tenant, attempt, "withdrawal", "withdrawn", {"confirmed": True}) == first
    )
    with pytest.raises(Conflict):
        append_event(url, tenant, attempt, "withdrawal", "withdrawn", {"confirmed": False})


def test_concurrent_import_preserves_same_ids_and_events(publication_db):
    from webapp.publications.ledger import import_history

    url, owners, _ = publication_db
    tenant = owners[0][0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: import_history(
                    url, tenant, "source", [item()], evidence({"source": [item()]})
                ),
                range(2),
            )
        )
    assert results[0] == results[1]
    with db.connect(url) as con:
        assert con.execute("SELECT COUNT(*) AS n FROM publication_events").fetchone()["n"] == 1


def test_partial_import_never_opens_cut_and_cut_cannot_be_weakened(publication_db):
    from webapp.publications.ledger import history_ready, import_history

    url, owners, _ = publication_db
    tenant = owners[0][0]
    sources = {"db1": [item()], "db2": [item(2)], "db3": [], "manual": [item(3)]}
    proof = evidence(sources)
    import_history(url, tenant, "db1", [item()], proof)
    assert not history_ready(url, tenant, "facebook:7")
    weaker = evidence({"db1": [item()]})
    with pytest.raises(Conflict):
        import_history(url, tenant, "db1", [item()], weaker)
    for source, rows in list(sources.items())[1:]:
        import_history(url, tenant, source, rows, proof)
    assert history_ready(url, tenant, "facebook:7")
    assert not history_ready(url, owners[1][0], "facebook:7")
    assert not history_ready(url, tenant, "facebook:8")


@pytest.mark.parametrize("state", ["failed", "uncertain", "inflight", "attempt_started", "held"])
def test_attempt_states_preserved_without_authorization(publication_db, state):
    from webapp.publications.ledger import history_ready, import_history, seen_media

    url, owners, _ = publication_db
    tenant = owners[0][0]
    row = item(state=state)
    result = import_history(url, tenant, "legacy", [row], evidence({"legacy": [row]}))
    assert result["items"][0]["state"] == state
    assert seen_media(url, tenant, "facebook:7", "a" * 64) is (state != "held")
    assert history_ready(url, tenant, "facebook:7") is (
        state not in {"uncertain", "inflight", "attempt_started"}
    )
    with db.connect(url) as con:
        assert con.execute("SELECT * FROM publication_revisions").fetchall() == []
        assert con.execute("SELECT * FROM publication_grants").fetchall() == []


def test_unmapped_history_retains_platform_without_blocking_proven_meta(publication_db):
    from webapp.publications.ledger import history_ready, import_history

    url, owners, _ = publication_db
    tenant = owners[0][0]
    rows = [item(), item(2, None, destination_candidate="x:123")]
    result = import_history(url, tenant, "source", rows, evidence({"source": rows}))
    assert result["items"][1]["hold_reason"] == "destination_mapping_required"
    assert history_ready(url, tenant, "facebook:7")
    assert not history_ready(url, tenant, "x:123")


def test_import_without_cut_manifest_never_means_ready(publication_db):
    from webapp.publications.ledger import history_ready, import_history

    url, owners, _ = publication_db
    tenant = owners[0][0]
    import_history(
        url, tenant, "legacy", [item()], {"source_sha256": "b" * 64, "receipt_sha256": "c" * 64}
    )
    assert not history_ready(url, tenant, "facebook:7")


def test_new_unmanifested_source_cannot_hide_behind_closed_cut(history_db):
    from webapp.publications.ledger import history_ready, import_history

    url, tenant, _ = history_db
    assert history_ready(url, tenant, "facebook:7")
    import_history(
        url,
        tenant,
        "new-source",
        [item(2)],
        {"source_sha256": "d" * 64, "receipt_sha256": "e" * 64},
    )
    assert not history_ready(url, tenant, "facebook:7")


def test_alias_added_after_history_import_cannot_bypass_guard(publication_db):
    from webapp.publications.ledger import import_history, seen_media

    url, owners, _ = publication_db
    tenant = owners[0][0]
    legacy = item(destination="facebook:old-profile")
    plain = {"source_sha256": "b" * 64, "receipt_sha256": "c" * 64}
    import_history(url, tenant, "legacy", [legacy], plain)
    proof = evidence({"legacy": [legacy]})
    proof["cut_manifest"]["aliases"] = [
        {
            "alias": "facebook:old-profile",
            "destination": "facebook:7",
            "evidence": {"same_photo_id": "123"},
        }
    ]
    import_history(url, tenant, "legacy", [legacy], proof)
    assert seen_media(url, tenant, "facebook:7", "a" * 64)


def test_confirmed_reconciliation_closes_uncertain_cut_without_rewriting_origin(publication_db):
    from webapp.publications.ledger import append_event, history_ready, import_history, seen_media

    url, owners, _ = publication_db
    tenant = owners[0][0]
    row = item(state="uncertain")
    result = import_history(url, tenant, "legacy", [row], evidence({"legacy": [row]}))
    attempt = result["items"][0]["attempt_id"]
    append_event(
        url,
        tenant,
        attempt,
        "reconcile:unconfirmed",
        "reconciled",
        {"state": "published", "confirmed": False},
    )
    assert not history_ready(url, tenant, "facebook:7")
    append_event(
        url,
        tenant,
        attempt,
        "reconcile:confirmed",
        "reconciled",
        {"state": "published", "confirmed": True, "receipt": {"remote_id": "123"}},
    )
    assert history_ready(url, tenant, "facebook:7")
    assert seen_media(url, tenant, "facebook:7", "a" * 64)
    with db.connect(url) as con:
        assert (
            con.execute(
                "SELECT state FROM publication_history WHERE tenant_id=?", (tenant,)
            ).fetchone()["state"]
            == "uncertain"
        )


def test_runtime_attempt_cannot_change_account_or_image_after_start(publication_db):
    from webapp.publications.ledger import append_event

    url, owners, _ = publication_db
    tenant = owners[0][0]
    payload = {"normalized_destination": "facebook:7", "image_sha256": "a" * 64}
    append_event(url, tenant, "runtime:test", "start", "attempt_started", payload)
    with pytest.raises(Conflict):
        append_event(
            url,
            tenant,
            "runtime:test",
            "publish",
            "published",
            {**payload, "normalized_destination": "facebook:8"},
        )


def test_transaction_seams_share_reads_and_roll_back_event_and_guard(history_db):
    from webapp.publications.ledger import (
        append_event_in_transaction,
        history_ready_in_transaction,
        seen_media,
        seen_media_in_transaction,
    )
    from webapp.publications.policies import lock_tenant

    url, tenant, _ = history_db
    with db.connect(url) as con:
        lock_tenant(con, tenant)
        assert history_ready_in_transaction(con, tenant, "facebook:7")
        assert seen_media_in_transaction(con, tenant, "facebook:7", "a" * 64)
        append_event_in_transaction(
            con,
            tenant,
            "runtime:rollback",
            "start",
            "attempt_started",
            {"normalized_destination": "facebook:7", "image_sha256": "d" * 64},
        )
        assert seen_media_in_transaction(con, tenant, "facebook:7", "d" * 64)
        con.rollback()
    assert not seen_media(url, tenant, "facebook:7", "d" * 64)
    with db.connect(url) as con:
        assert (
            con.execute(
                "SELECT * FROM publication_events WHERE tenant_id=? AND attempt_id='runtime:rollback'",
                (tenant,),
            ).fetchall()
            == []
        )


@pytest.mark.parametrize(
    "new_alias,new_target", [("facebook:7", "facebook:8"), ("facebook:other", "facebook:old")]
)
def test_alias_chains_across_cuts_cannot_bypass_destination_guards(
    publication_db, new_alias, new_target
):
    from webapp.publications.ledger import import_history

    url, owners, _ = publication_db
    tenant = owners[0][0]
    row = item()
    first = evidence({"source": [row]})
    first["cut_manifest"]["aliases"] = [
        {"alias": "facebook:old", "destination": "facebook:7", "evidence": {"same_photo": "1"}}
    ]
    import_history(url, tenant, "source", [row], first)
    next_proof = evidence({"source": [row]}, cut_id="another-cut")
    next_proof["cut_manifest"]["aliases"] = [
        {"alias": new_alias, "destination": new_target, "evidence": {"same_photo": "2"}}
    ]
    with pytest.raises(Conflict):
        import_history(url, tenant, "source", [row], next_proof)


def test_history_rows_events_cuts_sources_and_guards_are_sql_immutable(history_db):
    import sqlite3

    import psycopg

    url, tenant, _ = history_db
    for table, column in (
        ("publication_history", "state"),
        ("publication_events", "kind"),
        ("publication_history_sources", "source_sha256"),
        ("publication_history_cuts", "manifest_hash"),
        ("publication_media_guards", "image_sha256"),
    ):
        for operation in (
            f"UPDATE {table} SET {column}='replaced' WHERE tenant_id=?",
            f"DELETE FROM {table} WHERE tenant_id=?",
        ):
            with (
                pytest.raises((sqlite3.IntegrityError, psycopg.errors.RaiseException)),
                db.connect(url) as con,
            ):
                con.execute(operation, (tenant,))


def test_append_guard_for_trusted_runtime_attempt_and_tenant_isolation(publication_db):
    from webapp.publications.ledger import append_event, seen_media

    url, owners, _ = publication_db
    tenant = owners[0][0]
    append_event(
        url,
        tenant,
        "runtime:test",
        "start",
        "attempt_started",
        {"normalized_destination": "facebook:7", "image_sha256": "a" * 64},
    )
    assert seen_media(url, tenant, "facebook:7", "a" * 64)
    with pytest.raises(NotFound):
        append_event(
            url, owners[1][0], "history:missing", "withdraw", "withdrawn", {"confirmed": True}
        )


def test_source_mutation_and_batch_error_roll_back(publication_db):
    from webapp.publications.contracts import InvalidInput
    from webapp.publications.ledger import import_history

    url, owners, _ = publication_db
    tenant = owners[0][0]
    import_history(url, tenant, "legacy", [item()], evidence({"legacy": [item()]}))
    with pytest.raises(Conflict):
        import_history(
            url,
            tenant,
            "legacy",
            [item(caption="mutated")],
            {"source_sha256": "b" * 64, "receipt_sha256": "c" * 64},
        )
    with pytest.raises(InvalidInput):
        import_history(
            url,
            tenant,
            "other",
            [item(2), item(3, image_sha256="bad")],
            {"source_sha256": "b" * 64, "receipt_sha256": "c" * 64},
        )
    with db.connect(url) as con:
        assert con.execute("SELECT COUNT(*) AS n FROM publication_history").fetchone()["n"] == 1


def test_inventory_dryrun_and_two_applies_preserve_22_rows_four_withdrawals(publication_db):
    from scripts.import_publication_history import import_inventories
    from webapp.publications.ledger import history_ready, seen_media

    url, owners, _ = publication_db
    tenant = owners[0][0]
    root = Path(__file__).resolve().parents[2]
    inventory = root / "docs/MIGRACION-HUMANIZAR-INVENTARIO-20261011.json"
    manual = root / "docs/MIGRACION-HUMANIZAR-MANUALES-20261011.json"
    preview = import_inventories(url, tenant, inventory, manual)
    assert preview["dry_run"] is True and preview["counts"] == {
        "deliveries": 22,
        "published": 14,
        "held": 8,
        "withdrawals": 4,
        "unmapped": 2,
    }
    with db.connect(url) as con:
        assert con.execute("SELECT * FROM publication_history").fetchall() == []
    first = import_inventories(url, tenant, inventory, manual, apply=True)
    assert import_inventories(url, tenant, inventory, manual, apply=True) == first
    with db.connect(url) as con:
        rows = con.execute("SELECT * FROM publication_history ORDER BY id").fetchall()
        events = con.execute("SELECT * FROM publication_events ORDER BY id").fetchall()
        assert len(rows) == 22 and len(events) == 26
        assert sum(row["kind"] == "withdrawn" for row in events) == 4
        assert sum(row["state"] == "held" for row in rows) == 8
        assert len({row["attempt_id"] for row in rows}) == 22
        assert con.execute("SELECT * FROM publication_revisions").fetchall() == []
    for dest in (
        "facebook:1045986888587355",
        "facebook:110421192090737",
        "instagram:17841434345672986",
    ):
        assert history_ready(url, tenant, dest)
        assert seen_media(
            url, tenant, dest, "0484a5bb0259f2c78d2b9a7d8871d7e925863507fbb11a1899373a3ebcec7580"
        )
    for alias in ("facebook:100093808513344", "facebook:1008644758939132"):
        assert seen_media(
            url, tenant, alias, "0484a5bb0259f2c78d2b9a7d8871d7e925863507fbb11a1899373a3ebcec7580"
        )
    assert not history_ready(url, tenant, "x:2107177185962299392")
    assert not history_ready(url, tenant, "tiktok:user3217463593302")


def test_inventory_alias_evidence_cannot_be_faked(publication_db, tmp_path):
    from scripts.import_publication_history import import_inventories
    from webapp.publications.contracts import InvalidInput

    url, owners, _ = publication_db
    root = Path(__file__).resolve().parents[2]
    manual = json.loads((root / "docs/MIGRACION-HUMANIZAR-MANUALES-20261011.json").read_text())
    manual["facebook_alias_proof"]["native_original_permalink_photo_id"] = "different-photo"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(manual))
    with pytest.raises(InvalidInput):
        import_inventories(
            url,
            owners[0][0],
            root / "docs/MIGRACION-HUMANIZAR-INVENTARIO-20261011.json",
            bad,
            apply=True,
        )


def test_history_migration_rolls_back_and_keeps_no_seed(isolated_db, monkeypatch):
    from webapp.publications.migrations import migrate_publications

    db.init_db(isolated_db)
    tables = (
        "publication_media_guards",
        "publication_events",
        "publication_history",
        "publication_history_sources",
        "publication_history_cuts",
    )
    with db.connect(isolated_db) as con:
        for table in tables:
            con.execute(f"DROP TABLE {table}")
        con.execute("DELETE FROM schema_migrations WHERE version='publication_history_v1'")
    execute = db.DualConnection.execute

    def fail_marker(self, sql, params=()):
        if (
            sql.startswith("INSERT INTO schema_migrations")
            and params[0] == "publication_history_v1"
        ):
            raise RuntimeError("injected-history-marker")
        return execute(self, sql, params)

    with monkeypatch.context() as patch:
        patch.setattr(db.DualConnection, "execute", fail_marker)
        with pytest.raises(RuntimeError, match="injected-history-marker"):
            migrate_publications(isolated_db)
    with db.connect(isolated_db) as con:
        if con.dialect == "sqlite":
            assert (
                con.execute(
                    "SELECT name FROM sqlite_master WHERE name='publication_history'"
                ).fetchone()
                is None
            )
        else:
            assert (
                con.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name='publication_history'"
                ).fetchone()
                is None
            )
    migrate_publications(isolated_db)
    migrate_publications(isolated_db)
    with db.connect(isolated_db) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM schema_migrations WHERE version='publication_history_v1'"
            ).fetchone()["n"]
            == 1
        )
        for table in tables:
            assert con.execute(f"SELECT * FROM {table}").fetchall() == []
