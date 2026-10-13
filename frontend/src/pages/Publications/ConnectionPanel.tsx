import { useState } from "react";
import { ApiError, beginSessionWork } from "../../api/client";
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
const names: Record<Platform, string> = { facebook: "Facebook", instagram: "Instagram", tiktok: "TikTok", x: "X" };
const modes: Record<Platform, string[]> = {
  facebook: ["page", "facebook_login"],
  instagram: ["instagram_login", "facebook_login"],
  tiktok: ["oauth2"],
  x: ["oauth2"],
};
function navigateOAuth(
  authorizationUrl: string,
  work: ReturnType<typeof beginSessionWork>,
) {
  const url = new URL(authorizationUrl);
  const hosts = [
    "www.facebook.com",
    "www.instagram.com",
    "www.tiktok.com",
    "twitter.com",
    "x.com",
  ];
  if (
    url.protocol !== "https:" || url.username || url.password ||
    !hosts.includes(url.hostname)
  )
    throw new Error("OAuth no disponible");
  work.check();
  window.location.assign(url.href);
}
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
  const onboarding = platform === "tiktok" && mode === "oauth2";
  const create = async () => {
    const work = beginSessionWork(operation.current.signal);
    setBusy(true);
    setError("");
    try {
      work.check();
      const projectIds = projects.split(",").map((p) => Number(p.trim()));
      if (onboarding) {
        if (
          projects.split(",").some((p) => !/^\d+$/.test(p.trim())) ||
          projectIds.some((id) => !Number.isSafeInteger(id) || id <= 0)
        )
          throw new ApiError(422, "Indica IDs de proyectos válidos, mayores que cero y separados por coma.");
        const result = await publicationRequest<{ authorization_url: string }>(
          "/oauth/onboarding/start",
          "POST",
          {
            platform: "tiktok",
            api_mode: "oauth2",
            project_ids: projectIds,
            redirect_uri: window.location.origin + "/api/v1/publications/oauth/callback",
          },
          work.signal,
        );
        navigateOAuth(result.authorization_url, work);
        return;
      }
      await publicationRequest(
        "/connections",
        "POST",
        {
          platform,
          api_mode: mode,
          remote_id: remote,
          project_ids: projectIds,
        },
        work.signal,
      );
      work.check();
      onRefresh?.();
    } catch (e) {
      if (!work.signal.aborted && !isAbort(e)) setError(errorMessage(e));
    } finally {
      if (!work.signal.aborted) setBusy(false);
      work.finish();
    }
  };
  const connect = async (c: Connection) => {
    const work = beginSessionWork(operation.current.signal);
    setBusy(true);
    setError("");
    try {
      work.check();
      const result = await publicationRequest<{ authorization_url: string }>(
        "/oauth/start",
        "POST",
        {
          platform: c.platform,
          connection_id: c.id,
          redirect_uri:
            window.location.origin + "/api/v1/publications/oauth/callback",
        },
        work.signal,
      );
      navigateOAuth(result.authorization_url, work);
    } catch (e) {
      if (!work.signal.aborted && !isAbort(e)) setError(errorMessage(e));
    } finally {
      if (!work.signal.aborted) setBusy(false);
      work.finish();
    }
  };
  return (
    <section className="pub-accounts" aria-labelledby="accounts-heading">
      <h2 id="accounts-heading">Cuentas de la empresa</h2>
      <p>Conectar una cuenta permite revisar sus permisos. Cada envío necesita su propia decisión y requisitos.</p>
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
            <p className="pub-account-status">{names[c.platform]} · {c.expires_at && c.expires_at <= Date.now() / 1000 ? "Conexión vencida" : c.status === "active" ? "Conectada" : "Conexión pendiente o retenida"}</p>
            {c.expires_at && (
              <p>Vence: {new Date(c.expires_at * 1000).toLocaleString()}</p>
            )}
            <details>
              <summary>Permisos y datos de la cuenta</summary>
              <p>ID remoto: {c.remote_id} · Cuenta {c.id}</p>
              <p>Proyectos autorizados: {c.project_ids.join(", ")}</p>
            <p>
              Permisos:{" "}
              {c.scopes.length
                ? c.scopes.join(", ")
                : "Sin permisos comprobados"}
            </p>
            </details>
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
        {(Object.keys(names) as Platform[]).filter(p => !connections.some(c => c.platform === p)).map(p => <li key={p} className="pub-account-unconnected">
          <h3>{names[p]}</h3><p>Sin conectar</p>
          <p>Añade una cuenta de esta red para iniciar su conexión.</p>
        </li>)}
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
            {!onboarding && <label>
              ID remoto de cuenta
              <input
                value={remote}
                required
                pattern="[A-Za-z0-9_-]{1,128}"
                onChange={(e) => setRemote(e.target.value)}
              />
            </label>}
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
              {onboarding
                ? "TikTok identificará tu cuenta al autorizar su conexión. Una sola cuenta puede servir a varios proyectos."
                : "Una sola cuenta canónica puede servir a varios productos. Añadirla no verifica permisos: completa después OAuth."}
            </p>
            <Button type="submit">Añadir cuenta</Button>
          </fieldset>
        </form>
      </details>
    </section>
  );
}
