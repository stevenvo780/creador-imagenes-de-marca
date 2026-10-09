#!/usr/bin/env python3
"""Fence de rollback PostgreSQL: auditoría por defecto, sin DSN en argumentos/salida.

Operación administrativa global y explícita, nunca hook de startup/release.
DATABASE_URL se entrega mediante el canal privado del operador.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import psycopg
from psycopg import sql

FENCE_NAME = "eikon_rollback_no_active_scoped_keys"
_FENCE_EXPRESSION = "((scopes_json IS NULL) OR (revoked_at IS NOT NULL))"


def _fence_active(con: psycopg.Connection[Any], schema: str) -> bool:
    row = con.execute(
        "SELECT c.contype, c.convalidated, c.connoinherit, pg_catalog.pg_get_expr(c.conbin, c.conrelid) "
        "FROM pg_catalog.pg_constraint c "
        "JOIN pg_catalog.pg_class t ON t.oid = c.conrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = t.relnamespace "
        "WHERE n.nspname = %s AND t.relname = 'api_keys' AND c.conname = %s",
        (schema, FENCE_NAME),
    ).fetchone()
    if row is None:
        return False
    if row != ("c", True, False, _FENCE_EXPRESSION):
        raise ValueError("el nombre reservado corresponde a otra restricción")
    return True


def operate(
    db_url: str,
    action: str = "audit",
    *,
    schema: str = "public",
    legacy_unreachable_confirmed: bool = False,
) -> dict[str, Any]:
    """Revoca todos los scopes (incluso vacíos/expirados) y bloquea nuevas emisiones.

    ACCESS EXCLUSIVE primero: espera escritores anteriores y bloquea los nuevos
    hasta que revocación y CHECK se confirman juntos. Disarm nunca reactiva keys.
    El flag de disarm es una declaración del operador, no una prueba de tráfico.
    """
    if not isinstance(db_url, str) or not db_url.startswith(("postgresql://", "postgres://")):
        raise ValueError("se requiere PostgreSQL explícito")
    if action not in {"audit", "arm", "disarm"} or not schema or "\x00" in schema:
        raise ValueError("operación o schema inválido")
    if action == "disarm" and legacy_unreachable_confirmed is not True:
        raise ValueError("disarm requiere confirmar que legacy es inaccesible")
    table = sql.Identifier(schema, "api_keys")
    revoked = 0
    with psycopg.connect(db_url, application_name="eikon-rollback-scoped-keys") as con:
        if action == "audit":
            con.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        con.execute("SET LOCAL lock_timeout = '10s'")
        con.execute("SET LOCAL statement_timeout = '60s'")
        lock = "ACCESS SHARE" if action == "audit" else "ACCESS EXCLUSIVE"
        con.execute(sql.SQL("LOCK TABLE {} IN " + lock + " MODE").format(table))
        # También fija AccessShare durante audit: counts y catálogo ven el mismo fence.
        counts = con.execute(
            sql.SQL(
                "SELECT count(*) FILTER (WHERE scopes_json IS NOT NULL AND revoked_at IS NULL), "
                "count(*) FILTER (WHERE scopes_json IS NULL AND revoked_at IS NULL) FROM {}"
            ).format(table)
        ).fetchone()
        if counts is None:
            raise RuntimeError("auditoría sin resultado")
        active = _fence_active(con, schema)
        if action == "arm":
            revoked = con.execute(
                sql.SQL(
                    "UPDATE {} SET revoked_at = %s WHERE scopes_json IS NOT NULL AND revoked_at IS NULL"
                ).format(table),
                (int(time.time()),),
            ).rowcount
            if not active:
                con.execute(
                    sql.SQL(
                        "ALTER TABLE {} ADD CONSTRAINT {} "
                        "CHECK (scopes_json IS NULL OR revoked_at IS NOT NULL)"
                    ).format(table, sql.Identifier(FENCE_NAME))
                )
            active = _fence_active(con, schema)
        elif action == "disarm" and active:
            con.execute(
                sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}").format(
                    table, sql.Identifier(FENCE_NAME)
                )
            )
            active = False
        result = {
            "action": action,
            "fence_active": active,
            "unrevoked_scoped": counts[0] - revoked,
            "active_legacy": counts[1],
            "revoked_now": revoked,
        }
    # No recibo de éxito hasta que termina el COMMIT.
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "arm", "disarm"), nargs="?", default="audit")
    parser.add_argument("--schema", default="public")
    parser.add_argument("--legacy-unreachable-confirmed", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = operate(
            os.environ.get("DATABASE_URL", ""),
            args.action,
            schema=args.schema,
            legacy_unreachable_confirmed=args.legacy_unreachable_confirmed,
        )
    except Exception:
        # psycopg puede incluir DSN/datos en excepciones: no imprimirlas ni encadenarlas.
        print(
            "Operación no confirmada; revisar conexión PostgreSQL, permisos, locks y fence en privado.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
