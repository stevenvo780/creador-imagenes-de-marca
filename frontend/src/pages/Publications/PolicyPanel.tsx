import { Button } from "../../components";
import { useState } from "react";
import {
  Policy,
  errorMessage,
  isAbort,
  policyInput,
  publicationRequest,
} from "../../api/publications";
import { usePrivateOperation } from "../Media/usePrivateOperation";
export function PolicyPanel({
  policy,
  owner,
  onRefresh,
}: {
  policy: Policy;
  owner: boolean;
  onRefresh: () => void;
}) {
  const initial = policyInput(policy),
    [draft, setDraft] = useState(initial),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const operation = usePrivateOperation();
  const save = async (stop = false) => {
    setBusy(true);
    setError("");
    try {
      await publicationRequest(
        "/policy",
        "POST",
        {
          ...(stop ? { enabled: false } : draft),
          expected_version: policy.version,
        },
        operation.current.signal,
      );
      onRefresh();
    } catch (e) {
      if (!isAbort(e)) setError(errorMessage(e));
    } finally {
      if (!operation.current.signal.aborted) setBusy(false);
    }
  };
  return (
    <section aria-labelledby="policy-heading">
      <h2 id="policy-heading">Autonomía editorial</h2>
      <p>
        Política {policy.version} · {policy.enabled ? "Activa" : "Detenida"}. La
        IA decide pertinencia; cada red mantiene sus propios requisitos.
      </p>
      {error && <p role="alert">{error}</p>}
      {owner && (
        <>
          <Button
            className="pub-stop"
            disabled={busy || !policy.enabled}
            onClick={() => save(true)}
          >
            Detener autonomía
          </Button>
          <details>
            <summary>Editar alcance y vigencia</summary>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                save();
              }}
            >
              <fieldset disabled={busy}>
                <label>
                  <input
                    type="checkbox"
                    checked={draft.enabled}
                    onChange={(e) =>
                      setDraft({ ...draft, enabled: e.target.checked })
                    }
                  />{" "}
                  Habilitar autonomía dentro de esta política
                </label>
                {(
                  ["project_ids", "product_ids", "connection_ids"] as const
                ).map((k) => (
                  <label key={k}>
                    {
                      {
                        project_ids: "Proyectos autorizados (IDs)",
                        product_ids: "Productos autorizados (IDs)",
                        connection_ids: "Cuentas autorizadas (IDs)",
                      }[k]
                    }
                    <input
                      required
                      defaultValue={draft[k].join(", ")}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          [k]: e.target.value
                            .split(",")
                            .map((v) => Number(v.trim()))
                            .filter((v) => v > 0),
                        })
                      }
                    />
                  </label>
                ))}
                <label>
                  Fuentes permitidas, una URL por línea
                  <textarea
                    required
                    value={draft.allowed_sources.join("\n")}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        allowed_sources: e.target.value.split("\n"),
                      })
                    }
                  />
                </label>
                <label>
                  Zona horaria
                  <input
                    required
                    value={draft.timezone}
                    onChange={(e) =>
                      setDraft({ ...draft, timezone: e.target.value })
                    }
                  />
                </label>
                {(
                  [
                    "frequency_minutes",
                    "max_daily_per_destination",
                    "window_minutes",
                  ] as const
                ).map((k) => (
                  <label key={k}>
                    {
                      {
                        frequency_minutes: "Intervalo mínimo (minutos)",
                        max_daily_per_destination: "Máximo diario por cuenta",
                        window_minutes: "Ventana de envío (minutos)",
                      }[k]
                    }
                    <input
                      type="number"
                      min="1"
                      required
                      value={draft[k]}
                      onChange={(e) =>
                        setDraft({ ...draft, [k]: Number(e.target.value) })
                      }
                    />
                  </label>
                ))}
                <label>
                  Vigente desde (ISO con zona)
                  <input
                    required={draft.enabled}
                    placeholder="2026-10-12T08:00:00-05:00"
                    value={draft.valid_from || ""}
                    onChange={(e) =>
                      setDraft({ ...draft, valid_from: e.target.value || null })
                    }
                  />
                </label>
                <label>
                  Vence (ISO con zona)
                  <input
                    required={draft.enabled}
                    value={draft.expires_at || ""}
                    onChange={(e) =>
                      setDraft({ ...draft, expires_at: e.target.value || null })
                    }
                  />
                </label>
                <p>
                  Gasto deshabilitado. Guardar crea otra versión y requiere
                  nuevas evaluaciones/concesiones.
                </p>
                <Button>Guardar nueva política</Button>
              </fieldset>
            </form>
          </details>
        </>
      )}
    </section>
  );
}
