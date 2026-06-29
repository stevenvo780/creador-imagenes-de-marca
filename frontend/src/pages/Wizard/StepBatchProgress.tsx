/**
 * Resultado: muestra progreso del batch encolado.
 * Hace polling a GET /api/v1/batches/{id} cada 2s.
 */
import { useEffect, useState } from "react";
import { batches, type Batch, ApiError } from "../../api/client";

interface StepBatchProgressProps {
  batchId: number;
  onCreateAnother: () => void;
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
          // Si aún está pending o running, sigue polleando
          if (b.status !== "done" && b.status !== "error") {
            setTimeout(poll, 2000);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.detail : "Error al obtener estado del batch.",
          );
          setLoading(false);
        }
      }
    };

    poll();
    return () => {
      cancelled = true;
    };
  }, [batchId]);

  if (loading) {
    return (
      <section style={{ display: "grid", gap: "var(--space-4)" }}>
        <div>
          <h2
            style={{
              margin: "0 0 var(--space-3)",
              fontSize: "var(--font-size-xl)",
              fontWeight: 700,
              color: "var(--color-text)",
            }}
          >
            Batch encolado
          </h2>
          <p
            style={{
              margin: "0",
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text-muted)",
            }}
            aria-live="polite"
          >
            Iniciando procesamiento…
          </p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section style={{ display: "grid", gap: "var(--space-4)" }}>
        <h2
          style={{
            margin: 0,
            fontSize: "var(--font-size-xl)",
            fontWeight: 700,
            color: "var(--color-error)",
          }}
        >
          Error
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: "var(--font-size-sm)",
            color: "var(--color-error)",
            background: "var(--color-error-bg)",
            padding: "var(--space-3)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-error)",
          }}
          role="alert"
        >
          {error}
        </p>
        <button
          onClick={onCreateAnother}
          style={{
            padding: "var(--space-2) var(--space-4)",
            background: "var(--color-primary)",
            color: "#fff",
            border: "none",
            borderRadius: "var(--radius-md)",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Crear otro batch
        </button>
      </section>
    );
  }

  if (!batch) {
    return null;
  }

  const statusColor = {
    pending: "var(--color-text-muted)",
    running: "var(--color-primary)",
    done: "#22c55e",
    error: "var(--color-error)",
  }[batch.status];

  const statusLabel = {
    pending: "En espera",
    running: "Procesando",
    done: "Completado",
    error: "Error",
  }[batch.status];

  const isComplete = batch.status === "done" || batch.status === "error";

  return (
    <section style={{ display: "grid", gap: "var(--space-4)" }}>
      <div>
        <h2
          style={{
            margin: "0 0 var(--space-3)",
            fontSize: "var(--font-size-xl)",
            fontWeight: 700,
            color: "var(--color-text)",
          }}
        >
          Batch #{batch.id} encolado
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
          }}
        >
          Creado: {new Date(batch.created_at || "").toLocaleString()}
        </p>
      </div>

      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-md)",
          padding: "var(--space-4)",
          display: "grid",
          gap: "var(--space-3)",
        }}
      >
        <div>
          <p
            style={{
              margin: "0 0 var(--space-2)",
              fontSize: "var(--font-size-sm)",
              fontWeight: 600,
              color: "var(--color-text)",
            }}
          >
            Estado
          </p>
          <div
            style={{
              display: "inline-block",
              padding: "var(--space-2) var(--space-3)",
              background: "var(--color-bg)",
              border: `2px solid ${statusColor}`,
              borderRadius: "var(--radius-md)",
              fontSize: "var(--font-size-sm)",
              fontWeight: 600,
              color: statusColor,
            }}
          >
            {statusLabel}
          </div>
        </div>

        {batch.status === "running" && (
          <div>
            <p
              style={{
                margin: "0 0 var(--space-2)",
                fontSize: "var(--font-size-sm)",
                fontWeight: 600,
                color: "var(--color-text)",
              }}
            >
              Progreso
            </p>
            <div
              style={{
                background: "var(--color-bg)",
                borderRadius: "var(--radius-sm)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "8px",
                  background: "var(--color-primary)",
                  animation: "pulse 1.5s ease-in-out infinite",
                }}
              />
            </div>
            <style>{`
              @keyframes pulse {
                0%, 100% { opacity: 0.6; }
                50% { opacity: 1; }
              }
            `}</style>
            {batch.counts && typeof batch.counts === "object" && (
              <p
                style={{
                  margin: "var(--space-2) 0 0",
                  fontSize: "var(--font-size-sm)",
                  color: "var(--color-text-muted)",
                }}
              >
                Renderizado: {(batch.counts as Record<string, number>).rendered || 0}, Rankeado:{" "}
                {(batch.counts as Record<string, number>).ranked || 0}
              </p>
            )}
          </div>
        )}

        {batch.status === "done" && (
          <div
            style={{
              background: "rgba(34,197,94,0.08)",
              padding: "var(--space-3)",
              borderRadius: "var(--radius-md)",
              borderLeft: "4px solid #22c55e",
            }}
          >
            <p
              style={{
                margin: 0,
                fontSize: "var(--font-size-sm)",
                color: "#166534",
                fontWeight: 600,
              }}
            >
              Generación completada exitosamente.
            </p>
            {batch.counts && typeof batch.counts === "object" && (
              <p
                style={{
                  margin: "var(--space-1) 0 0",
                  fontSize: "var(--font-size-sm)",
                  color: "#166534",
                }}
              >
                Total: {(batch.counts as Record<string, number>).rendered || 0} variaciones
              </p>
            )}
          </div>
        )}

        {batch.status === "error" && (
          <div
            style={{
              background: "var(--color-error-bg)",
              padding: "var(--space-3)",
              borderRadius: "var(--radius-md)",
              borderLeft: "4px solid var(--color-error)",
            }}
          >
            <p
              style={{
                margin: 0,
                fontSize: "var(--font-size-sm)",
                color: "var(--color-error)",
                fontWeight: 600,
              }}
            >
              Hubo un error durante el procesamiento.
            </p>
          </div>
        )}

        {batch.finished_at && (
          <p
            style={{
              margin: 0,
              fontSize: "var(--font-size-xs)",
              color: "var(--color-text-muted)",
            }}
          >
            Finalizado: {new Date(batch.finished_at).toLocaleString()}
          </p>
        )}
      </div>

      {isComplete && (
        <div style={{ display: "grid", gap: "var(--space-2)", gridTemplateColumns: "1fr 1fr" }}>
          <button
            onClick={() => window.location.href = `/gallery?batch=${batch.id}`}
            style={{
              padding: "var(--space-3) var(--space-4)",
              background: "var(--color-primary)",
              color: "#fff",
              border: "none",
              borderRadius: "var(--radius-md)",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Ver resultados
          </button>
          <button
            onClick={onCreateAnother}
            style={{
              padding: "var(--space-3) var(--space-4)",
              background: "var(--color-surface)",
              border: "1.5px solid var(--color-border)",
              borderRadius: "var(--radius-md)",
              fontWeight: 600,
              cursor: "pointer",
              color: "var(--color-text)",
            }}
          >
            Crear otro batch
          </button>
        </div>
      )}

      {batch.status === "running" && (
        <p
          style={{
            margin: 0,
            fontSize: "var(--font-size-xs)",
            color: "var(--color-text-muted)",
            textAlign: "center",
          }}
          aria-live="polite"
        >
          Actualizando…
        </p>
      )}
    </section>
  );
}
