"""Transportes oficiales sin redirects autenticados ni cuerpos remotos públicos."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import replace
from pathlib import Path

import httpx

from .connections import REQUIRED_SCOPES
from .contracts import Conflict, canonical_hash
from .oauth import OAuthConfig, VerifiedAccount

# Endpoints fijos por modo; configuración privada no puede añadir hosts.
_HOSTS = {
    "facebook": {"graph.facebook.com"},
    "instagram": {"graph.instagram.com", "api.instagram.com"},
    "tiktok": {"open.tiktokapis.com"},
    "x": {"api.x.com"},
}


def read_private_file(path: str | Path) -> bytes:
    """Archivo regular propio, sin symlink y sin lectura de grupo/otros."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
                or info.st_size > 65536
            ):
                raise ValueError
            return stream.read(65537)
    except (OSError, ValueError) as exc:
        raise Conflict("private_configuration_unavailable") from exc


def load_provider_configs(path: str | None) -> dict[tuple[str, str], OAuthConfig]:
    if not path:
        raise Conflict("oauth_not_configured")
    try:
        payload = json.loads(read_private_file(path))
        if not isinstance(payload, list):
            raise ValueError
        configs = {}
        for value in payload:
            # Los scopes/hosts nunca se amplían desde el archivo del owner.
            if set(value) - {
                "platform",
                "api_mode",
                "client_id",
                "client_secret",
                "redirect_uris",
                "graph_version",
            }:
                raise ValueError
            value = {**value, "redirect_uris": tuple(value["redirect_uris"])}
            config = OAuthConfig(**value)
            config.public()
            pair = (config.platform, config.api_mode)
            if pair in configs:
                raise ValueError
            configs[pair] = config
        return configs
    except (Conflict, ValueError, TypeError, KeyError) as exc:
        raise Conflict("oauth_not_configured") from exc


class OfficialOAuthClient:
    """Red por HTTPTransport: sin log de URL/tokens del cliente de alto nivel.

    MockTransport en tests sustituye únicamente la red. Las verificaciones,
    selección de página, scopes y expiración se ejecutan realmente.
    """

    def __init__(self, config: OAuthConfig, transport: httpx.BaseTransport | None = None):
        config.public()
        self.config = config
        self._sensitive_material = {config.client_secret}
        self.transport = transport or httpx.HTTPTransport(retries=0, trust_env=False)

    def close(self) -> None:
        self.transport.close()

    def _remember_secrets(self, value: dict | list) -> None:
        """Retiene material confidencial aunque luego se sustituya la credencial.

        El conjunto nunca forma parte de JSON, metadatos ni del vault. También
        cubre respuestas anidadas (IG corto y las páginas de Meta).
        """
        if isinstance(value, dict):
            for key, item in value.items():
                if (
                    key
                    in {
                        "access_token",
                        "refresh_token",
                        "id_token",
                        "client_secret",
                        "code",
                        "code_verifier",
                        "input_token",
                    }
                    and isinstance(item, str)
                    and item
                ):
                    self._sensitive_material.add(item)
                elif isinstance(item, (dict, list)):
                    self._remember_secrets(item)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (dict, list)):
                    self._remember_secrets(item)

    def _request(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        params: dict | None = None,
        data: dict | None = None,
        basic: tuple[str, str] | None = None,
    ) -> dict:
        host = httpx.URL(url).host
        allowed = (
            _HOSTS["facebook"]
            if self.config.api_mode == "facebook_login" or self.config.platform == "facebook"
            else _HOSTS[self.config.platform]
        )
        if httpx.URL(url).scheme != "https" or host not in allowed:
            raise Conflict("provider_verification_failed")
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if basic:
            import base64

            headers["Authorization"] = (
                "Basic " + base64.b64encode((basic[0] + ":" + basic[1]).encode()).decode()
            )
        self._remember_secrets(params or {})
        self._remember_secrets(data or {})
        if token:
            self._sensitive_material.add(token)
        if headers.get("Authorization"):
            self._sensitive_material.add(headers["Authorization"])
        request = httpx.Request(
            method,
            url,
            params=params,
            data=data,
            headers=headers,
            extensions={"timeout": {"connect": 10.0, "read": 15.0, "write": 15.0, "pool": 10.0}},
        )
        response = self.transport.handle_request(request)
        try:
            # Una redirección, aun a otro host oficial, se retiene; no se sigue.
            if response.status_code != 200:
                raise Conflict("provider_verification_failed")
            body = b""
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > 1024 * 1024:
                    raise Conflict("provider_verification_failed")
            result = json.loads(body)
            if not isinstance(result, dict):
                raise Conflict("provider_verification_failed")
            error = result.get("error")
            if error and (not isinstance(error, dict) or error.get("code") != "ok"):
                raise Conflict("provider_verification_failed")
            self._remember_secrets(result)
            return result
        except (ValueError, TypeError) as exc:
            raise Conflict("provider_verification_failed") from exc
        finally:
            response.close()

    def _flow(self, flow: dict) -> None:
        if flow["platform"] != self.config.platform or flow["api_mode"] != self.config.api_mode:
            raise Conflict("oauth_not_configured")
        if "client_id" in flow and (
            flow["client_id"] != self.config.client_id
            or flow.get("graph_version") != self.config.graph_version
            or canonical_hash({k: flow[k] for k in self.config.public()})
            != canonical_hash(self.config.public())
        ):
            raise Conflict("oauth_not_configured")
        if self.config.platform == "x" and not self.config.spend_allowed:
            raise Conflict("blocked_budget")

    def exchange(self, flow: dict, code: str, verifier: str | None) -> dict:
        self._flow(flow)
        if flow["redirect_uri"] not in self.config.redirect_uris:
            raise Conflict("oauth_not_configured")
        config = self.config
        form = {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code": code,
            "redirect_uri": flow["redirect_uri"],
            "grant_type": "authorization_code",
        }
        if config.platform == "facebook" or config.api_mode == "facebook_login":
            result = self._request(
                "POST",
                f"https://graph.facebook.com/{config.graph_version}/oauth/access_token",
                data=form,
            )
        elif config.platform == "instagram":
            result = self._request(
                "POST", "https://api.instagram.com/oauth/access_token", data=form
            )
            if "data" in result:
                entries = result["data"]
                if (
                    "access_token" in result
                    or not isinstance(entries, list)
                    or len(entries) != 1
                    or not isinstance(entries[0], dict)
                ):
                    raise Conflict("provider_verification_failed")
                result = entries[0]
            short_token = result.get("access_token")
            if not isinstance(short_token, str) or not short_token:
                raise Conflict("provider_verification_failed")
            result = self._request(
                "GET",
                "https://graph.instagram.com/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": config.client_secret,
                    "access_token": short_token,
                },
            )
        elif config.platform == "tiktok":
            form["client_key"] = form.pop("client_id")
            result = self._request("POST", "https://open.tiktokapis.com/v2/oauth/token/", data=form)
        else:
            if not verifier:
                raise Conflict("provider_verification_failed")
            form.pop("client_secret")
            form["code_verifier"] = verifier
            result = self._request(
                "POST",
                "https://api.x.com/2/oauth2/token",
                data=form,
                basic=(config.client_id, config.client_secret),
            )
        if not isinstance(result.get("access_token"), str) or not result["access_token"]:
            raise Conflict("provider_verification_failed")
        # Esta marca vive solo en memoria del transporte, nunca se importa como autoridad.
        self._exchange_result = result
        return result

    def _expiry_from_exchange(self, credential: dict, now: int) -> tuple[int | None, str]:
        if credential is not getattr(self, "_exchange_result", None):
            return None, "unknown"
        expires = credential.get("expires_in")
        if type(expires) is not int or expires <= 0:
            return None, "unknown"
        return now + expires, "known"

    def _debug_meta(self, token: str, host: str) -> dict:
        result = self._request(
            "GET",
            f"https://{host}/{self.config.graph_version}/debug_token",
            token=self.config.client_id + "|" + self.config.client_secret,
            params={"input_token": token},
        ).get("data")
        if (
            not isinstance(result, dict)
            or result.get("is_valid") is not True
            or str(result.get("app_id")) != self.config.client_id
        ):
            raise Conflict("provider_verification_failed")
        return result

    def _meta_expiry(self, debug: dict) -> tuple[int | None, str]:
        expiry = debug.get("expires_at")
        access = debug.get("data_access_expires_at")
        if type(expiry) is not int or expiry < 0:
            return None, "unknown"
        if access is not None and (type(access) is not int or access < 0):
            return None, "unknown"
        dates = [v for v in (expiry, access) if type(v) is int and v > 0]
        return (min(dates), "known") if dates else (None, "non_expiring")

    def verify(self, flow: dict, credential: dict, now: int) -> VerifiedAccount:
        self._remember_secrets(credential)
        account = self._verify_account(flow, credential, now)
        return replace(account, sensitive_material=tuple(sorted(self._sensitive_material)))

    def _verify_account(self, flow: dict, credential: dict, now: int) -> VerifiedAccount:
        self._flow(flow)
        token = credential.get("access_token")
        if not isinstance(token, str) or not token:
            raise Conflict("provider_verification_failed")
        platform, mode = self.config.platform, self.config.api_mode
        if platform == "facebook" or mode == "facebook_login":
            return self._verify_meta(flow, credential, now)
        if platform == "instagram":
            return self._verify_instagram_login(flow, credential, now)
        if platform == "tiktok":
            data = (
                self._request(
                    "GET",
                    "https://open.tiktokapis.com/v2/user/info/",
                    token=token,
                    params={"fields": "open_id,display_name"},
                )
                .get("data", {})
                .get("user", {})
            )
            expiry, state = self._expiry_from_exchange(credential, now)
            # Importar scope/expires_in declarados en fichero NO es evidencia.
            scopes = (
                tuple(credential["scope"].split(","))
                if credential is getattr(self, "_exchange_result", None)
                and isinstance(credential.get("scope"), str)
                else ()
            )
            if credential is getattr(self, "_exchange_result", None) and credential.get(
                "open_id"
            ) != data.get("open_id"):
                raise Conflict("provider_verification_failed")
            return VerifiedAccount(
                str(data.get("open_id") or ""),
                data.get("display_name", ""),
                scopes,
                expiry,
                state,
                ("open.tiktokapis.com",),
                {k: credential[k] for k in ("access_token", "refresh_token") if k in credential},
                "token_exchange",
            )
        data = self._request("GET", "https://api.x.com/2/users/me", token=token).get("data", {})
        expiry, state = self._expiry_from_exchange(credential, now)
        scopes = (
            tuple(credential["scope"].split())
            if credential is getattr(self, "_exchange_result", None)
            and isinstance(credential.get("scope"), str)
            else ()
        )
        return VerifiedAccount(
            str(data.get("id") or ""),
            data.get("name", ""),
            scopes,
            expiry,
            state,
            ("api.x.com",),
            {k: credential[k] for k in ("access_token", "refresh_token") if k in credential},
            "token_exchange",
        )

    def _verify_instagram_login(self, flow: dict, credential: dict, now: int) -> VerifiedAccount:
        token = credential["access_token"]
        base = f"https://graph.instagram.com/{self.config.graph_version}"
        identity = self._request(
            "GET", base + "/me", token=token, params={"fields": "user_id,username"}
        )
        # `id` es app-scoped: solo `user_id` identifica al profesional.
        remote = identity.get("user_id")
        if (
            not isinstance(remote, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", remote)
            or remote != flow["expected_remote_id"]
        ):
            raise Conflict("provider_verification_failed")
        probe = self._request(
            "GET",
            base + f"/{remote}/content_publishing_limit",
            token=token,
            params={"fields": "quota_usage,config"},
        ).get("data")
        if not isinstance(probe, list) or len(probe) != 1 or not isinstance(probe[0], dict):
            raise Conflict("provider_verification_failed")
        item = probe[0]
        quota = item.get("config")
        if not isinstance(quota, dict):
            raise Conflict("provider_verification_failed")
        usage, total, duration = (
            item.get("quota_usage"),
            quota.get("quota_total"),
            quota.get("quota_duration"),
        )
        if (
            type(usage) is not int
            or usage < 0
            or type(total) is not int
            or total <= 0
            or type(duration) is not int
            or duration <= 0
        ):
            raise Conflict("provider_verification_failed")
        if usage >= total:
            raise Conflict("provider_verification_failed")
        # Inferencia explícita del acceso al endpoint: no lista de todos los scopes.
        scopes = tuple(sorted(REQUIRED_SCOPES[("instagram", "instagram_login")]))
        expiry, state = self._expiry_from_exchange(credential, now)
        return VerifiedAccount(
            remote,
            identity.get("username", ""),
            scopes,
            expiry,
            state,
            ("graph.instagram.com",),
            {"access_token": token},
            "capability_probe",
        )

    def _verify_meta(self, flow: dict, credential: dict, now: int) -> VerifiedAccount:
        base = f"https://graph.facebook.com/{self.config.graph_version}"
        token = credential["access_token"]
        expected = flow["expected_remote_id"]
        debug = self._debug_meta(token, "graph.facebook.com")
        if debug.get("type") == "USER":
            # Selección exacta del destino: /me personal nunca se guarda como página.
            pages = self._request(
                "GET",
                base + "/me/accounts",
                token=token,
                params={
                    "fields": "id,name,access_token,tasks,instagram_business_account{id,username}",
                    "limit": "100",
                },
            ).get("data", [])
            match = []
            for p in pages:
                if not isinstance(p, dict):
                    continue
                remote = (
                    p.get("id")
                    if self.config.platform == "facebook"
                    else p.get("instagram_business_account", {}).get("id")
                )
                if str(remote) == expected and "CREATE_CONTENT" in p.get("tasks", []):
                    match.append(p)
            if len(match) != 1:
                raise Conflict("provider_verification_failed")
            token = match[0]["access_token"]
            debug = self._debug_meta(token, "graph.facebook.com")
        if debug.get("type") != "PAGE":
            raise Conflict("provider_verification_failed")
        page = self._request(
            "GET",
            base + "/me",
            token=token,
            params={"fields": "id,name,instagram_business_account{id,username}"},
        )
        identity = (
            page
            if self.config.platform == "facebook"
            else page.get("instagram_business_account", {})
        )
        remote = str(identity.get("id") or "")
        scopes = list(debug.get("scopes", []))
        # Un scope granular autorizado para otra página no habilita ésta.
        for grant in debug.get("granular_scopes", []):
            targets = grant.get("target_ids")
            if targets is not None and str(page.get("id")) not in [str(v) for v in targets]:
                scopes = [s for s in scopes if s != grant.get("scope")]
        expiry, state = self._meta_expiry(debug)
        name = (
            identity.get("name", "")
            if self.config.platform == "facebook"
            else identity.get("username", "")
        )
        return VerifiedAccount(
            remote,
            name,
            tuple(scopes),
            expiry,
            state,
            ("graph.facebook.com",),
            {"access_token": token},
        )
