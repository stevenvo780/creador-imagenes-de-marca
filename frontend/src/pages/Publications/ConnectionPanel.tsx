import { useState } from "react";
import {
  Connection,
  Platform,
  errorMessage,
  isAbort,
  publicationRequest,
} from "../../api/publications";
import { Button } from "../../components";
import { usePrivateOperation } from "../Media/usePrivateOperation";
const reasons: Record<string, string> = {
  authorization_required: "Completa la conexión OAuth con el owner.",
  requires_auth: "Reconecta la cuenta.",
  needs_platform_consent: "Completa el consentimiento de la pieza.",
  needs_platform_audit: "Falta acreditar auditoría o revisión de TikTok.",
  blocked_budget: "X permanece bloqueado por gasto no autorizado.",
};
const modes: Record<Platform, string[]> = {
  facebook: ["page", "facebook_login"],
  instagram: ["instagram_login", "facebook_login"],
  tiktok: ["oauth2"],
  x: ["oauth2"],
};
export function ConnectionPanel({
  connections,
  onRefresh,
}: {
  connections: Connection[];
  onRefresh?: () => void;
}) {
  const [platform, setPlatform] = useState<Platform>("facebook"),
    [mode, setMode] = useState("page"),
    [remote, setRemote] = useState(""),
    [projects, setProjects] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const operation = usePrivateOperation();
  const create = async () => {
    setBusy(true);
    setError("");
    try {
      await publicationRequest(
        "/connections",
        "POST",
        {
          platform,
          api_mode: mode,
          remote_id: remote,
          project_ids: projects.split(",").map((p) => Number(p.trim())),
        },
        operation.current.signal,
      );
      onRefresh?.();
    } catch (e) {
      if (!isAbort(e)) setError(errorMessage(e));
    } finally {
      if (!operation.current.signal.aborted) setBusy(false);
    }
  };
  const connect = async (c: Connection) => {
    setBusy(true);
    setError("");
    try {
      const result = await publicationRequest<{ authorization_url: string }>(
        "/oauth/start",
        "POST",
        {
          platform: c.platform,
          connection_id: c.id,
          redirect_uri:
            window.location.origin + "/api/v1/publications/oauth/callback",
        },
        operation.current.signal,
      );
      const url = new URL(result.authorization_url);
      const hosts = [
        "www.facebook.com",
        "www.instagram.com",
        "www.tiktok.com",
        "twitter.com",
        "x.com",
      ];
      if (
        url.protocol !== "https:" ||
        url.username ||
        url.password ||
        !hosts.includes(url.hostname)
      )
        throw new Error("OAuth no disponible");
      window.location.assign(url.href);
    } catch (e) {
      if (!isAbort(e)) setError(errorMessage(e));
    } finally {
      if (!operation.current.signal.aborted) setBusy(false);
    }
  };
  return (
    <section aria-labelledby="accounts-heading">
      <h2 id="accounts-heading">Cuentas y requisitos</h2>
      {error && <p role="alert">{error}</p>}
      {!connections.length && (
        <p>
          No hay cuentas conectadas. El owner debe conectar las redes de esta
          empresa.
        </p>
      )}
      <ul className="pub-connections">
        {connections.map((c) => (
          <li key={c.id}>
            <h3>{c.remote_name || c.remote_id}</h3>
            <p>
              {c.platform} · {c.remote_id} · cuenta {c.id}
            </p>
            <p>Proyectos: {c.project_ids.join(", ")}</p>
            <p>
              {c.status === "active" ? "Conexión activa" : "Conexión retenida"}
            </p>
            {c.expires_at && (
              <p>Vence: {new Date(c.expires_at * 1000).toLocaleString()}</p>
            )}
            <p>
              Permisos:{" "}
              {c.scopes.length
                ? c.scopes.join(", ")
                : "Sin permisos comprobados"}
            </p>
            {c.hold_reason && <p>{reasons[c.hold_reason] || c.hold_reason}</p>}
            {c.platform === "tiktok" && (
              <p>
                TikTok requiere consentimiento por contenido. La publicación
                pública requiere auditoría acreditada.
              </p>
            )}
            {c.platform === "x" && <p>{reasons.blocked_budget}</p>}
            <Button disabled={busy} onClick={() => connect(c)}>
              Conectar o renovar permisos
            </Button>
          </li>
        ))}
      </ul>
      <details>
        <summary>Añadir cuenta para varios proyectos</summary>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create();
          }}
        >
          <fieldset disabled={busy}>
            <label>
              Red
              <select
                value={platform}
                onChange={(e) => {
                  const p = e.target.value as Platform;
                  setPlatform(p);
                  setMode(modes[p][0]);
                }}
              >
                {Object.keys(modes).map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
            <label>
              Modo de conexión
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                {modes[platform].map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </label>
            <label>
              ID remoto de cuenta
              <input
                value={remote}
                required
                pattern="[A-Za-z0-9_-]{1,128}"
                onChange={(e) => setRemote(e.target.value)}
              />
            </label>
            <label>
              Proyectos autorizados (IDs separados por coma)
              <input
                required
                pattern="[0-9, ]+"
                value={projects}
                onChange={(e) => setProjects(e.target.value)}
              />
            </label>
            <p>
              Una sola cuenta canónica puede servir a varios productos. Añadirla
              no verifica permisos: completa después OAuth.
            </p>
            <Button type="submit">Añadir cuenta</Button>
          </fieldset>
        </form>
      </details>
    </section>
  );
}
