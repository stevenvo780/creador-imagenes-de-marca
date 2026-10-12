"""Formato congelado nuevo, sin reescribir contratos históricos (SQLite/PG)."""

import json

import pytest

from webapp import db
from webapp.publications.campaigns import get_revision
from webapp.publications.contracts import InvalidInput, canonical_hash, canonical_json
from webapp.tests.test_publication_campaigns import (
    campaign,
    campaign_case,
    campaign_clients,
    freeze,
    isolated_db,
)

__all__ = ["campaign_case", "campaign_clients", "isolated_db"]


def test_format_frozen_hash_and_repeated_read(campaign_case):
    url, (a, _), _app = campaign_case
    c = campaign(url, a)
    feed = freeze(url, a, c)
    assert feed["snapshot"]["channel_metadata"]["publication_format"] == "feed"
    reel = freeze(url, a, c, channel_metadata={"publication_format": "reel"})
    assert reel["snapshot"]["channel_metadata"]["publication_format"] == "reel"
    assert feed["contract_hash"] != reel["contract_hash"]
    assert get_revision(url, a["tenant"], feed["id"])["snapshot"] == feed["snapshot"]
    with pytest.raises(InvalidInput):
        freeze(url, a, c, channel_metadata={"publication_format": "invented"})


def test_old_formatless_snapshot_not_rehashed(campaign_case):
    url, (a, _), _app = campaign_case
    frozen = freeze(url, a, campaign(url, a))
    legacy = json.loads(frozen["frozen_json"])
    legacy["channel_metadata"].pop("publication_format", None)
    # Crear fila histórica independiente vía SQL sólo fixture, sin UPDATE de revisión.
    with db.connect(url) as con:
        con.execute(
            "INSERT INTO publication_revisions(tenant_id,campaign_id,media_kind,gallery_image_id,connection_id,policy_version,scheduled_at_utc,contract_hash,frozen_json,created_at) SELECT tenant_id,campaign_id,media_kind,gallery_image_id,connection_id,policy_version,scheduled_at_utc,?,?,created_at FROM publication_revisions WHERE tenant_id=? AND id=?",
            (canonical_hash(legacy), canonical_json(legacy), a["tenant"], frozen["id"]),
        )
        rid = db.get_last_insert_id(url, con, "publication_revisions")
    loaded = get_revision(url, a["tenant"], rid)
    assert loaded["snapshot"] == legacy
    assert loaded["contract_hash"] == canonical_hash(legacy)
