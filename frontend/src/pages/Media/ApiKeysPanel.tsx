import { usePrivateOperation } from "./usePrivateOperation";
import { useEffect, useState, type FormEvent } from "react";
import {
  codexScopes,
  createCodexKey,
  listCodexKeys,
  revokeCodexKey,
  mediaError,
  isAbort,
  type ApiKey,
} from "../../api/media";
import { Button, Modal } from "../../components";
const scopeLabels: Record<(typeof codexScopes)[number], string> = {
  "projects:read": "Consultar proyectos",
  "projects:write": "Crear y organizar proyectos",
  "brands:read": "Consultar identidad de marca",
  "briefs:write": "Crear encargos de generación",
  "media:read": "Consultar y descargar imágenes",
  "media:write": "Ingresar imágenes para revisión",
};
export function ApiKeysPanel({ onClose }: { onClose: () => void }) {
  const [keys, setKeys] = useState<ApiKey[]>([]),
    [secret, setSecret] = useState(""),
    [name, setName] = useState("Codex"),
    [days, setDays] = useState(30),
    [scopes, setScopes] = useState<string[]>([
      "brands:read",
      "projects:read",
      "media:read",
      "media:write",
    ]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const controller = usePrivateOperation();
  useEffect(() => {
    void listCodexKeys(controller.current.signal)
      .then((r) => setKeys(r.keys))
      .catch((e) => {
        if (!isAbort(e)) setError(mediaError(e));
      });
    return () => {
      controller.current.abort();
      setSecret("");
    };
  }, [controller]);
  function close() {
    setSecret("");
    controller.current.abort();
    onClose();
  }
  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSecret("");
    try {
      const r = await createCodexKey(
        { name: name.trim(), scopes, expires_in_days: days },
        controller.current.signal,
      );
      if (controller.current.signal.aborted) return;
      setSecret(r.key);
      setKeys((k) => [
        ...k,
        { id: r.id, name: r.name, scopes: r.scopes, expires_at: r.expires_at },
      ]);
    } catch (e) {
      if (!isAbort(e)) setError(mediaError(e));
    } finally {
      if (!controller.current.signal.aborted) setBusy(false);
    }
  }
  async function revoke(id: number) {
    setBusy(true);
    setError("");
    try {
      await revokeCodexKey(id, controller.current.signal);
      if (!controller.current.signal.aborted) {
        setKeys((k) =>
          k.map((item) => (item.id === id ? { ...item, revoked: true } : item)),
        );
        setSecret("");
      }
    } catch (e) {
      if (!isAbort(e)) setError(mediaError(e));
    } finally {
      if (!controller.current.signal.aborted) setBusy(false);
    }
  }
  return (
    <Modal open onClose={close} title="Conectar Codex">
      <p>
        Cada empresa usa su propia conexión. Estas claves no pueden aprobar
        imágenes ni administrar otras claves.
      </p>
      {error && <p role="alert">{error}</p>}
      {secret ? (
        <div role="status">
          <p>
            Guardá esta clave ahora: sólo se muestra una vez. Al cerrar se borra
            de esta pantalla.
          </p>
          <label htmlFor="codex-secret">Clave nueva</label>
          <textarea
            id="codex-secret"
            readOnly
            value={secret}
            autoComplete="off"
          />
          <Button onClick={close}>Cerrar y borrar clave</Button>
        </div>
      ) : (
        <form className="media-form" onSubmit={(e) => void create(e)}>
          <label>
            Nombre de la conexión
            <input
              required
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            Vigencia en días
            <input
              type="number"
              required
              min={1}
              max={365}
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            />
          </label>
          <fieldset>
            <legend>Permisos de Codex</legend>
            {codexScopes.map((scope) => (
              <label className="media-checkbox" key={scope}>
                <input
                  type="checkbox"
                  checked={scopes.includes(scope)}
                  onChange={(e) =>
                    setScopes((s) =>
                      e.target.checked
                        ? [...s, scope]
                        : s.filter((v) => v !== scope),
                    )
                  }
                />
                {scopeLabels[scope]}
              </label>
            ))}
          </fieldset>
          <Button type="submit" busy={busy}>
            Crear clave
          </Button>
        </form>
      )}
      <h3>Conexiones de esta empresa</h3>
      {keys.length === 0 ? (
        <p>No hay claves creadas.</p>
      ) : (
        <ul className="media-key-list">
          {keys.map((k) => (
            <li key={k.id}>
              <span>
                {k.name} ·{" "}
                {k.revoked
                  ? "Revocada"
                  : `Vence ${new Date(k.expires_at * 1000).toLocaleDateString("es")}`}
              </span>
              {!k.revoked && (
                <Button
                  variant="danger"
                  busy={busy}
                  onClick={() => void revoke(k.id)}
                >
                  Revocar {k.name}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
