"""Registro diferido sin dependencias API/storage/renderer ni red real."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path


def test_shared_normalizer_uses_only_stdlib_and_contracts():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import importlib.abc
                import json
                import sys

                class PureNormalizer(importlib.abc.MetaPathFinder):
                    def find_spec(self, fullname, path=None, target=None):
                        if fullname.startswith("webapp.") and fullname not in {
                            "webapp.publications", "webapp.publications.contracts",
                            "webapp.publications.provider_results",
                        }:
                            raise ImportError("normalizer_dependency_forbidden:" + fullname)

                sys.meta_path.insert(0, PureNormalizer())
                from webapp.publications.provider_results import _provider_result
                value = {"state": "held", "remote_id": None, "permalink": None,
                         "evidence": {"error_code": "authorization_failed"}}
                assert _provider_result(value, "facebook") == value
                assert "webapp.db" not in sys.modules
                print(json.dumps(value))
                """
            ),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "state": "held",
        "remote_id": None,
        "permalink": None,
        "evidence": {"error_code": "authorization_failed"},
    }


def test_api_preserves_shared_normalizer_alias():
    from webapp.publications.deliveries import _provider_result as api_normalizer
    from webapp.publications.provider_results import _provider_result

    assert api_normalizer is _provider_result


def test_save_report_in_worker_runtime_without_api_storage_or_renderer(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import hashlib
                import importlib.abc
                import json
                import sys
                from pathlib import Path

                blocked = ("webapp.api", "webapp.storage_backend", "eikon_core", "variations")

                class WorkerOnly(importlib.abc.MetaPathFinder):
                    def find_spec(self, fullname, path=None, target=None):
                        if any(fullname == name or fullname.startswith(name + ".") for name in blocked):
                            raise ImportError("worker_dependency_forbidden:" + fullname)

                sys.meta_path.insert(0, WorkerOnly())
                import httpx
                from publisher_worker.client import WorkerClient, _save_report
                from publisher_worker.outbox import Outbox, encoded

                # db/policies ya importados por connections al arrancar; sin conexión/migración.
                before = set(sys.modules)
                requests = []

                def report(request):
                    assert request.method == "POST"
                    assert request.url.path == "/api/v1/publications/worker/attempts/attempt%3A1/reports" or request.url.path == "/api/v1/publications/worker/attempts/attempt:1/reports"
                    body = json.loads(request.content)
                    assert set(body) == {"event_key", "result"}
                    requests.append(body)
                    # Sólo ACK del informe sintético; nunca autorización ni publicación real.
                    return httpx.Response(200, json={"state": "uncertain"})

                client = WorkerClient("https://worker.invalid", "SYNTHETIC_TOKEN",
                                      tenant_id=7, http=httpx.Client(transport=httpx.MockTransport(report)))
                box = Outbox(Path(sys.argv[1]) / "outbox.sqlite3", tenant_id=7)
                claim = {"attempt_id": "attempt:1"}
                assert box.reserve(claim, {"tenant_id": 7})
                valid = {"state": "published", "remote_id": "42_99",
                         "permalink": "https://www.facebook.com/42/posts/99",
                         "evidence": {"receipt_sha256": "a" * 64, "http_status": 200,
                                      "published_at": "2026-10-12T01:00:00+0000",
                                      "published_at_source": "provider"}}
                processing = {"state": "uncertain", "remote_id": None, "permalink": None,
                              "evidence": {"processing_kind": "facebook_upload", "processing_id": "123",
                                           "error_code": "processing_pending"}}
                held = {"state": "held", "remote_id": None, "permalink": None,
                        "evidence": {"error_code": "authorization_failed"}}
                fallback = {"state": "uncertain", "remote_id": None, "permalink": None,
                            "evidence": {"error_code": "status_unavailable"}}
                invalid = [
                    valid | {"evidence": {"raw": "SYNTHETIC_SECRET"}},
                    valid | {"remote_id": "https://secret?token=SYNTHETIC_SECRET"},
                    valid | {"permalink": "https://www.facebook.com/42?token=SYNTHETIC_SECRET"},
                    valid | {"evidence": {"http_status": True}},
                ]
                for value, expected in [(valid, valid), (processing, processing), (held, held)] + [(value, fallback) for value in invalid]:
                    saved = _save_report(client, box, claim, value, platform="facebook")
                    assert saved == expected
                    assert requests[-1]["result"] == expected
                    pending = {"result": expected, "confirmation": None}
                    assert requests[-1]["event_key"] == "worker:" + hashlib.sha256(encoded(pending).encode()).hexdigest()
                    entry = box.active()[0]
                    assert entry["result"] == expected and entry["pending"] is None
                    assert "SYNTHETIC_SECRET" not in str(entry) + str(requests)

                from webapp.publications.provider_results import _provider_result
                from webapp.publications.contracts import InvalidInput
                try:
                    _provider_result(invalid[1], "facebook")
                except InvalidInput as exc:
                    assert str(exc) == "invalid_remote_id"
                else:
                    raise AssertionError("invalid_result_accepted")
                added = set(sys.modules) - before
                assert "webapp.publications.deliveries" not in added
                assert not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules for prefix in blocked)
                client.close()
                print(json.dumps({"reports": len(requests), "states": [body["result"]["state"] for body in requests],
                                  "pending": box.active()[0]["pending"], "dependencies": "worker_only"}))
                """
            ),
            str(tmp_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "SYNTHETIC_SECRET" not in result.stdout + result.stderr
    assert "SYNTHETIC_TOKEN" not in result.stdout + result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "reports": 7,
        "states": [
            "published",
            "uncertain",
            "held",
            "uncertain",
            "uncertain",
            "uncertain",
            "uncertain",
        ],
        "pending": None,
        "dependencies": "worker_only",
    }
