#!/usr/bin/env python3
"""Import privado verificado, dry-run por defecto. No incluye ni busca secretos.

La ejecución productiva corresponde al controlador durante Task10, después
 del respaldo privado y del mapping explícito tenant/owner/cuenta/proyectos.
Entradas: archivo propio 0600 o stdin; nunca token/clave por argumentos CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Permite ejecución directa desde scripts/ conservando el paquete del checkout.
if __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from webapp import db
from webapp.publications.connections import _connection
from webapp.publications.contracts import Conflict, InvalidInput, PublicationError
from webapp.publications.oauth import import_credential
from webapp.publications.oauth_providers import (
    OfficialOAuthClient,
    load_provider_configs,
    read_private_file,
)
from webapp.publications.vault import service_key


def run_import(args, db_url, client, key, key_id, *, now=None) -> dict:
    raw = (
        sys.stdin.buffer.read(65537)
        if args.credential_file == "-"
        else read_private_file(args.credential_file)
    )
    try:
        if len(raw) > 65536:
            raise ValueError
        credential = json.loads(raw)
        if (
            not isinstance(credential, dict)
            or set(credential) - {"access_token", "refresh_token"}
            or not isinstance(credential.get("access_token"), str)
            or not credential["access_token"]
        ):
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise InvalidInput("invalid_credential_file") from exc
    return import_credential(
        db_url,
        args.tenant_id,
        args.owner_id,
        args.connection_id,
        credential,
        int(time.time()) if now is None else now,
        client,
        key=key,
        key_id=key_id,
        dry_run=not args.apply,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--owner-id", type=int, required=True)
    parser.add_argument("--connection-id", type=int, required=True)
    parser.add_argument(
        "--credential-file", required=True, help="archivo protegido o '-' para stdin"
    )
    parser.add_argument(
        "--config-file", default=os.environ.get("EIKON_PUBLICATION_OAUTH_CONFIG_FILE")
    )
    parser.add_argument(
        "--key-file", required=True, help="archivo protegido con clave AES-256 base64"
    )
    parser.add_argument("--key-id", required=True)
    parser.add_argument(
        "--db-file", help="SQLite de pruebas; para PostgreSQL usar DATABASE_URL privada"
    )
    parser.add_argument(
        "--apply", action="store_true", help="guardar solo después de verificación remota"
    )
    args = parser.parse_args(argv)
    client = None
    try:
        url = args.db_file or os.environ.get("DATABASE_URL")
        if not url:
            raise Conflict("database_not_configured")
        with db.connect(url) as con:
            row = _connection(con, args.tenant_id, args.connection_id)
        config = load_provider_configs(args.config_file).get((row["platform"], row["api_mode"]))
        if config is None:
            raise Conflict("oauth_not_configured")
        key = service_key(read_private_file(args.key_file).decode("ascii").strip())
        client = OfficialOAuthClient(config)
        result = run_import(args, url, client, key, args.key_id)
        # Recibo cerrado: ni JSON remoto ni material de vault salen por stdout.
        output = {
            "dry_run": not args.apply,
            "connection_id": args.connection_id,
            "eligible": result.get("eligible", result.get("status") == "active"),
            "hold_reason": result.get("hold_reason"),
        }
        print(json.dumps(output, sort_keys=True))
        return 0 if output["eligible"] else 2
    except (PublicationError, UnicodeError) as exc:
        print(
            json.dumps(
                {
                    "error": exc.code
                    if isinstance(exc, PublicationError)
                    else "private_configuration_unavailable"
                }
            )
        )
        return 2
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
