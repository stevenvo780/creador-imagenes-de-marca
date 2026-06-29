/**
 * Pantalla de progreso: muestra el estado de la generación en curso.
 * Polling a GET /api/v1/batches/{id} cada 2 segundos.
 */
import { useEffect, useState } from "react";
import { batches, type Batch, type BatchStatus, ApiError } from "../../api/client";
import { Button, Spinner } from "../../components";
import { formatDateTime } from "../../utils/format";

interface StepBatchProgressProps {
  batchId: number;
  onCreateAnother: () => void;
}

const STATUS_LABEL: Record<BatchStatus, string> = {
  pending:   "En cola…",
  running:   "Generando…",
  completed: "Listas",
  failed:    "Error",
  cancelled: "Cancelada",
};

const STATUS_COLOR: Record<BatchStatus, string> = {
  pending:   "var(--slate-500)",
  running:   "var(--teal-600)",
  completed: "#16a34a",
  failed:    "var(--error)",
  cancelled: "var(--slate-500)",
};

/** Estados terminales: ya no se sigue consultando el progreso. */
function isTerminal(status: BatchStatus): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

export function StepBatchProgress({
  batchId,
  onCreateAnother,
}: StepBatchProgressProps) {
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const b = await batches.get(batchId);
        if (!cancelled) {
          setBatch(b);
          setLoading(false);
          if (!isTerminal(b.status)) {
            setTimeout(poll, 2000);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.detail
              : "No se pudo obtener el estado de la generación.",
          );
          setLoading(false);
        }
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [batchId]);

  // ── Cargando inicial ─────────────────────────────────────────────────────────

  if (loading) {
    return (
      <section
        style={{
          display: "grid",
          gap: "var(--space-6)",
          textAlign: "center",
          padding: "var(--space-10) var(--space-6)",
        }}
      >
        <Spinner size="lg" />
        <p
          style={{
            margin: 0,
            fontFamily: "var(--font-display)",
            fontSize: "var(--font-size-xl)",
            fontWeight: 700,
            color: "var(--ink)",
          }}
          aria-live="polite"
        >
          Iniciando generación…
        </p>
        <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--slate-500)" }}>
          Esto puede tomar unos segundos.
        </p>
      </section>
    );
  }

  // ── Error de red ─────────────────────────────────────────────────────────────

  if (error) {
    return (
      <section style={{ display: "grid", gap: "var(--space-5)" }}>
        <h2
          style={{
            margin: 0,
            fontFamily: "var(--font-display)",
            fontSize: "var(--font-size-2xl)",
            fontWeight: 700,
            color: "var(--error)",
          }}
        >
          Algo salió mal
        </h2>
        <p
          role="alert"
          style={{
            margin: 0,
            fontSize: "var(--font-size-sm)",
            color: "var(--error)",
            background: "var(--error-bg)",
            padding: "var(--space-3) var(--space-4)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--error)",
          }}
        >
          {error}
        </p>
        <Button variant="secondary" onClick={onCreateAnother}>
          Volver al inicio
        </Button>
      </section>
    );
  }

  if (!batch) return null;

  const isComplete = isTerminal(batch.status);
  const isError = batch.status === "failed" || batch.status === "cancelled";
  const statusColor = STATUS_COLOR[batch.status] ?? "var(--slate-500)";
  const statusLabel = STATUS_LABEL[batch.status] ?? batch.status;
  const counts = batch.counts as Record<string, number> | undefined;

  return (
    <section style={{ display: "grid", gap: "var(--space-6)" }}>

      {/* Encabezado */}
      <div>
        <h2
          style={{
            margin: "0 0 var(--space-2)",
            fontFamily: "var(--font-display)",
            fontSize: "var(--font-size-2xl)",
            fontWeight: 700,
            color: "var(--ink)",
          }}
        >
          {batch.status === "completed"
            ? "¡Tus variaciones están listas!"
            : isError
              ? "No pudimos terminar"
              : "Generando tus variaciones…"}
        </h2>
        <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--slate-500)" }}>
          {batch.status === "completed"
            ? "El proceso terminó correctamente."
            : isError
              ? "El proceso se detuvo antes de terminar."
              : "Estamos trabajando en ello. Esto puede tardar un momento."}
        </p>
      </div>

      {/* Tarjeta de estado */}
      <div
        style={{
          background: "var(--white)",
          border: "1px solid var(--line)",
          borderRadius: "var(--radius-lg)",
          padding: "var(--space-5) var(--space-6)",
          display: "grid",
          gap: "var(--space-4)",
          boxShadow: "var(--shadow-sm)",
        }}
      >

        {/* Indicador de estado */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-3)",
          }}
        >
          {(batch.status === "pending" || batch.status === "running") && (
            <Spinner size="sm" />
          )}
          {batch.status === "completed" && (
            <span
              style={{
                width: "24px",
                height: "24px",
                borderRadius: "50%",
                background: "#16a34a",
                color: "#fff",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "var(--font-size-sm)",
                fontWeight: 700,
                flexShrink: 0,
              }}
              aria-hidden="true"
            >
              ✓
            </span>
          )}
          {isError && (
            <span
              style={{
                width: "24px",
                height: "24px",
                borderRadius: "50%",
                background: "var(--error)",
                color: "#fff",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "var(--font-size-sm)",
                fontWeight: 700,
                flexShrink: 0,
              }}
              aria-hidden="true"
            >
              ✕
            </span>
          )}
          <span
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "var(--font-size-lg)",
              fontWeight: 700,
              color: statusColor,
            }}
            aria-live="polite"
          >
            {statusLabel}
          </span>
        </div>

        {/* Barra de progreso animada (solo cuando está corriendo) */}
        {batch.status === "running" && (
          <div>
            <div
              style={{
                height: "6px",
                background: "var(--mist)",
                borderRadius: "var(--radius-pill)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  background:
                    "linear-gradient(90deg, var(--teal-600), var(--teal))",
                  borderRadius: "var(--radius-pill)",
                  animation: "eikon-pulse 1.5s ease-in-out infinite",
                  width: "100%",
                }}
              />
            </div>
            {counts && (
              <p
                style={{
                  margin: "var(--space-2) 0 0",
                  fontSize: "var(--font-size-xs)",
                  color: "var(--slate-500)",
                }}
                aria-live="polite"
              >
                {counts.rendered ?? 0} generadas · {counts.ranked ?? 0} evaluadas
              </p>
            )}
          </div>
        )}

        {/* Resultado exitoso */}
        {batch.status === "completed" && (
          <div
            style={{
              background: "rgba(22, 163, 74, 0.08)",
              padding: "var(--space-3) var(--space-4)",
              borderRadius: "var(--radius-md)",
              borderLeft: "4px solid #16a34a",
            }}
          >
            <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "#166534", fontWeight: 600 }}>
              Generación completada
            </p>
            {counts && (
              <p style={{ margin: "var(--space-1) 0 0", fontSize: "var(--font-size-sm)", color: "#166534" }}>
                {counts.rendered ?? 0} variaciones creadas
              </p>
            )}
          </div>
        )}

        {/* Resultado con error */}
        {isError && (
          <div
            style={{
              background: "var(--error-bg)",
              padding: "var(--space-3) var(--space-4)",
              borderRadius: "var(--radius-md)",
              borderLeft: "4px solid var(--error)",
            }}
          >
            <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--error)", fontWeight: 600 }}>
              Hubo un error durante la generación.
            </p>
            <p style={{ margin: "var(--space-1) 0 0", fontSize: "var(--font-size-sm)", color: "var(--error)" }}>
              Intenta de nuevo con una configuración distinta.
            </p>
          </div>
        )}

        {/* Fechas */}
        {batch.finished_at && (
          <p style={{ margin: 0, fontSize: "var(--font-size-xs)", color: "var(--slate-500)" }}>
            Finalizado: {formatDateTime(batch.finished_at)}
          </p>
        )}
      </div>

      {/* Acciones cuando termina */}
      {isComplete && (
        <div
          style={{
            display: "grid",
            gap: "var(--space-3)",
            gridTemplateColumns: batch.status === "completed" ? "2fr 1fr" : "1fr",
          }}
        >
          {batch.status === "completed" && (
            <Button
              variant="primary"
              onClick={() => { window.location.href = `/gallery?batch=${batch.id}`; }}
            >
              Ver mis variaciones →
            </Button>
          )}
          <Button variant="secondary" onClick={onCreateAnother}>
            Generar de nuevo
          </Button>
        </div>
      )}

      {/* Mensaje de espera */}
      {batch.status === "running" && (
        <p
          style={{
            margin: 0,
            fontSize: "var(--font-size-xs)",
            color: "var(--slate-500)",
            textAlign: "center",
          }}
          aria-live="polite"
        >
          Actualizando automáticamente…
        </p>
      )}
    </section>
  );
}
