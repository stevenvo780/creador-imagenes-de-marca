"""Entrypoint explícito; las unidades se instalan inicialmente deshabilitadas."""

import json
import os
import time
from pathlib import Path

from .adapters.base import HTTPTransport
from .adapters.facebook import FacebookAdapter
from .adapters.instagram import InstagramAdapter
from .adapters.tiktok import TikTokAdapter
from .adapters.x import XAdapter
from .client import WorkerClient, run_once
from .outbox import Outbox


def main():
    if os.environ.get("EIKON_PUBLISHER_ENABLED") != "1":
        print(json.dumps({"state": "disabled"}))
        return
    transport, client = None, None
    try:
        tenant = int(os.environ["EIKON_PUBLISHER_TENANT"])
        token = Path(os.environ["EIKON_PUBLISHER_TOKEN_FILE"]).read_text().strip()
        graph = os.environ["EIKON_PUBLISHER_GRAPH_VERSION"]
        client = WorkerClient(os.environ["EIKON_PUBLISHER_ORIGIN"], token, tenant_id=tenant)
        box = Outbox(os.environ["EIKON_PUBLISHER_OUTBOX"], tenant_id=tenant)
        transport = HTTPTransport()
        adapters = {
            "facebook": FacebookAdapter(transport, graph_version=graph),
            "instagram": InstagramAdapter(transport, graph_version=graph),
            "x": XAdapter(transport),
            "tiktok": TikTokAdapter(transport),
        }
        result = run_once(client, box, adapters, lambda: int(time.time()))
        # Sin URLs, tokens, cuerpos ni respuestas del proveedor en stdout.
        print(json.dumps({"state": result["state"], "processed": len(result["results"])}))
    except Exception:
        print(json.dumps({"state": "held", "reason": "worker_configuration_or_transport"}))
        raise SystemExit(1) from None
    finally:
        if client:
            client.close()
        if transport:
            transport.close()


if __name__ == "__main__":
    main()
