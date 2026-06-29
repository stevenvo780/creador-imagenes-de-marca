/**
 * Pantalla de progreso de una generación (ruta /batch/:batchId).
 * Sigue el avance en tiempo real (SSE) y muestra los resultados al terminar.
 * Lenguaje humano: "generación" en vez de "batch", calidad con estrellas
 * (componente Stars) en vez del número crudo de score.
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { batches, downloads, type Batch, type Variation, ApiError } from "../api/client";
import { Button, Spinner, Stars } from "../components";

interface ProgressData {
  rendered: number;
  ranked: number;
}

interface SSEEvent {
  type: "started" | "progress" | "completed" | "error";
  data?: Record<string, unknown>;
}

type UiStatus = "loading" | "rendering" | "done" | "error";

export function BatchProgressPage() {
  const { batchId } = useParams<{ batchId: string }>();
  const [loading, setLoading] = useState(true);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [variations, setVariations] = useState<Variation[]>([]);
  const [progress, setProgress] = useState<ProgressData>({ rendered: 0, ranked: 0 });
  const [uiStatus, setUiStatus] = useState<UiStatus>("loading");
  const [error, setError] = useState("");

  // Cargar la generación inicial
  useEffect(() => {
    if (!batchId) return;
    let cancelled = false;
    batches
      .get(Number(batchId))
      .then((res) => {
        if (cancelled) return;
        setBatch(res);
        // El backend usa completed/failed/cancelled.
        if (res.status === "completed") {
          setUiStatus("done");
        } else if (res.status === "failed" || res.status === "cancelled") {
          setUiStatus("error");
          setError("La generación no pudo completarse.");
        } else {
          setUiStatus("rendering");
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.detail : "No pudimos cargar la generación.",
          );
          setUiStatus("error");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [batchId]);

  // SSE: progreso en tiempo real
  useEffect(() => {
    if (!batchId || uiStatus === "done" || uiStatus === "error") return;
    let eventSource: EventSource | null = null;
    let cancelled = false;

    const url = `/api/v1/batches/${batchId}/events`;
    eventSource = new EventSource(url, { withCredentials: true });

    eventSource.onopen = () => {
      if (!cancelled) setUiStatus("rendering");
    };

    eventSource.addEventListener("message", (e) => {
      if (cancelled) return;
      try {
        const event: SSEEvent = JSON.parse(e.data);
        if (event.type === "started") {
          setProgress({ rendered: 0, ranked: 0 });
          setUiStatus("rendering");
        } else if (event.type === "progress") {
          const data = event.data as Record<string, number> | undefined;
          setProgress({
            rendered: data?.rendered ?? 0,
            ranked: data?.ranked ?? 0,
          });
        } else if (event.type === "completed") {
          setUiStatus("done");
          eventSource?.close();
          eventSource = null;
        } else if (event.type === "error") {
          const data = event.data as Record<string, unknown> | undefined;
          setError(String(data?.detail ?? "Ocurrió un error."));
          setUiStatus("error");
          eventSource?.close();
          eventSource = null;
        }
      } catch (err) {
        console.error("SSE parse error:", err);
      }
    });

    eventSource.onerror = () => {
      if (!cancelled) {
        // El servidor cierra el stream al terminar; lo tratamos como fin.
        eventSource?.close();
        eventSource = null;
      }
    };

    return () => {
      cancelled = true;
      eventSource?.close();
    };
  }, [batchId, uiStatus]);

  // Cargar variaciones cuando termina
  useEffect(() => {
    if (uiStatus !== "done" || !batchId || variations.length > 0) return;
    let cancelled = false;
    batches
      .variations(Number(batchId))
      .then((res) => {
        if (!cancelled) {
          const sorted = [...res.items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
          setVariations(sorted);
        }
      })
      .catch((err) => {
        if (!cancelled)
          setError(
            err instanceof ApiError ? err.detail : "No pudimos cargar las variaciones.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [uiStatus, batchId, variations.length]);

  async function handleDownloadVariation(v: Variation) {
    try {
      const res = await fetch(downloads.fileUrl(v.id), { credentials: "include" });
      if (!res.ok) throw new ApiError(res.status, "No pudimos descargar la imagen.");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `variacion-${v.id}.png`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof ApiError ? err.detail : "No pudimos descargar la imagen.");
    }
  }

  // ── Cargando ──────────────────────────────────────────────────────────────────
  if (loading)
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-3)",
          color: "var(--slate-500)",
          padding: "var(--space-10) 0",
        }}
        aria-live="polite"
        aria-busy="true"
      >
        <Spinner size="md" />
        Cargando tu generación…
      </div>
    );

  // ── Error ─────────────────────────────────────────────────────────────────────
  if (uiStatus === "error")
    return (
      <section style={{ display: "grid", gap: "var(--space-5)", maxWidth: 560 }}>
        <h1
          style={{
            margin: 0,
            fontFamily: "var(--font-display)",
            fontSize: "var(--font-size-2xl)",
            color: "var(--error)",
          }}
        >
          No pudimos terminar
        </h1>
        <p
          role="alert"
          style={{
            margin: 0,
            color: "var(--error)",
            background: "var(--error-bg)",
            padding: "var(--space-3) var(--space-4)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--error)",
            fontSize: "var(--font-size-sm)",
          }}
        >
          {error || "Ocurrió un error inesperado."}
        </p>
        <div>
          <Link to="/batch" style={{ textDecoration: "none" }}>
            <Button variant="primary">Intentar de nuevo</Button>
          </Link>
        </div>
      </section>
    );

  const total =
    (batch?.spec as Record<string, number>)?.count ??
    (batch?.counts as Record<string, number>)?.total ??
    Math.max(progress.rendered, 1);
  const percent = Math.min(100, Math.round((progress.rendered / total) * 100));

  return (
    <div style={{ display: "grid", gap: "var(--space-8)" }}>
      {/* Progreso */}
      {uiStatus === "rendering" && (
        <section
          aria-live="polite"
          aria-busy="true"
          aria-label="Progreso de la generación"
          style={{ display: "grid", gap: "var(--space-4)" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            <Spinner size="md" />
            <h1
              style={{
                margin: 0,
                fontFamily: "var(--font-display)",
                fontSize: "var(--font-size-2xl)",
                color: "var(--ink)",
              }}
            >
              Generando tus variaciones…
            </h1>
          </div>

          <div
            style={{
              height: "8px",
              background: "var(--mist)",
              borderRadius: "var(--radius-pill)",
              overflow: "hidden",
            }}
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${percent}% completado`}
          >
            <div
              style={{
                height: "100%",
                background: "linear-gradient(90deg, var(--teal-600), var(--teal))",
                width: `${percent}%`,
                borderRadius: "var(--radius-pill)",
                transition: "width 0.3s ease-in-out",
              }}
            />
          </div>
          <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--slate-500)" }}>
            {progress.rendered} de {total} listas · {percent}%
          </p>
        </section>
      )}

      {/* Resultados */}
      {uiStatus === "done" && variations.length > 0 && (
        <section>
          <h1
            style={{
              margin: "0 0 var(--space-6)",
              fontFamily: "var(--font-display)",
              fontSize: "var(--font-size-2xl)",
              color: "var(--ink)",
            }}
          >
            ¡Listas! {variations.length}{" "}
            {variations.length === 1 ? "variación" : "variaciones"}
          </h1>
          <ul
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
              gap: "var(--space-5)",
              listStyle: "none",
              margin: 0,
              padding: 0,
            }}
            aria-label="Variaciones generadas"
          >
            {variations.map((v) => (
              <li
                key={v.id}
                style={{
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--line)",
                  boxShadow: "var(--shadow-sm)",
                  overflow: "hidden",
                  background: "var(--white)",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <div style={{ background: "var(--mist)", padding: "var(--space-5)" }}>
                  <img
                    src={downloads.fileUrl(v.id)}
                    alt={`Vista previa de variación ${v.id}`}
                    loading="lazy"
                    style={{
                      display: "block",
                      width: "100%",
                      height: 180,
                      objectFit: "contain",
                    }}
                    onError={(e) => {
                      const img = e.currentTarget;
                      img.style.opacity = "0.25";
                      img.style.filter = "grayscale(1)";
                    }}
                  />
                </div>
                <div
                  style={{
                    padding: "var(--space-3) var(--space-4)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "var(--space-2)",
                    borderTop: "1px solid var(--line)",
                  }}
                >
                  <Stars score={v.score} />
                  <button
                    onClick={() => handleDownloadVariation(v)}
                    style={{
                      padding: "var(--space-1) var(--space-3)",
                      background: "var(--teal-600)",
                      color: "#fff",
                      border: "none",
                      borderRadius: "var(--radius-md)",
                      fontSize: "var(--font-size-xs)",
                      fontWeight: 600,
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                    }}
                    aria-label={`Descargar variación ${v.id}`}
                  >
                    ↓ Descargar
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Acción final */}
      {uiStatus === "done" && (
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap" }}>
          <Link to="/gallery" style={{ textDecoration: "none" }}>
            <Button variant="primary">Ver todas en la galería →</Button>
          </Link>
          <Link to="/batch" style={{ textDecoration: "none" }}>
            <Button variant="secondary">Generar de nuevo</Button>
          </Link>
        </div>
      )}
    </div>
  );
}
