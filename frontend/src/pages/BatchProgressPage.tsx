/**
 * Monitor de progreso de batch: SSE en tiempo real, barra de progreso,
 * grid de variaciones ordenadas por score (descendente).
 * Accesible (WCAG AA), responsive, estilos inline con tokens CSS.
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { batches, downloads, type Batch, type Variation, ApiError } from "../api/client";

interface ProgressData {
  rendered: number;
  ranked: number;
}

interface SSEEvent {
  type: "started" | "progress" | "completed" | "error";
  data?: Record<string, unknown>;
}

export function BatchProgressPage() {
  const { batchId } = useParams<{ batchId: string }>();
  const [loading, setLoading] = useState(true);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [variations, setVariations] = useState<Variation[]>([]);
  const [progress, setProgress] = useState<ProgressData>({ rendered: 0, ranked: 0 });
  const [batchStatus, setBatchStatus] = useState<"loading" | "rendering" | "done" | "error">(
    "loading"
  );
  const [error, setError] = useState("");

  // Cargar batch inicial
  useEffect(() => {
    if (!batchId) return;
    let cancelled = false;
    batches
      .get(Number(batchId))
      .then((res) => {
        if (!cancelled) {
          setBatch(res);
          // Si ya está done/error, saltea SSE
          if (res.status === "done") {
            setBatchStatus("done");
          } else if (res.status === "error") {
            setBatchStatus("error");
            setError("Batch falló durante render.");
          } else {
            setBatchStatus("rendering");
          }
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : "Error al cargar batch.");
          setBatchStatus("error");
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
    if (!batchId || batchStatus === "done" || batchStatus === "error") return;
    let eventSource: EventSource | null = null;
    let cancelled = false;

    const url = `/api/v1/batches/${batchId}/events`;
    eventSource = new EventSource(url, { withCredentials: true });

    eventSource.onopen = () => {
      if (!cancelled) setBatchStatus("rendering");
    };

    eventSource.addEventListener("message", (e) => {
      if (cancelled) return;
      try {
        const event: SSEEvent = JSON.parse(e.data);
        if (event.type === "started") {
          setProgress({ rendered: 0, ranked: 0 });
          setBatchStatus("rendering");
        } else if (event.type === "progress") {
          const data = event.data as Record<string, number> | undefined;
          setProgress({
            rendered: data?.rendered ?? 0,
            ranked: data?.ranked ?? 0,
          });
        } else if (event.type === "completed") {
          setBatchStatus("done");
          eventSource?.close();
          eventSource = null;
        } else if (event.type === "error") {
          const data = event.data as Record<string, unknown> | undefined;
          setError(String(data?.detail ?? "Error desconocido"));
          setBatchStatus("error");
          eventSource?.close();
          eventSource = null;
        }
      } catch (err) {
        console.error("SSE parse error:", err);
      }
    });

    eventSource.onerror = () => {
      if (!cancelled) {
        setError("Conexión SSE perdida.");
        setBatchStatus("error");
        eventSource?.close();
        eventSource = null;
      }
    };

    return () => {
      cancelled = true;
      eventSource?.close();
    };
  }, [batchId, batchStatus]);

  // Cargar variaciones cuando batch está done
  useEffect(() => {
    if (batchStatus !== "done" || !batchId || variations.length > 0) return;
    let cancelled = false;
    batches
      .variations(Number(batchId))
      .then((res) => {
        if (!cancelled) {
          const sorted = res.items.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
          setVariations(sorted);
        }
      })
      .catch((err) => {
        if (!cancelled)
          setError(
            err instanceof ApiError ? err.detail : "Error al cargar variaciones."
          );
      });
    return () => {
      cancelled = true;
    };
  }, [batchStatus, batchId, variations.length]);

  // Descarga individual de una variación
  async function handleDownloadVariation(v: Variation) {
    try {
      const res = await fetch(downloads.fileUrl(v.id), { credentials: "include" });
      if (!res.ok) throw new ApiError(res.status, "Error descargando");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `variacion-${v.id}.png`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof ApiError ? err.detail : "Error descargando variación.");
    }
  }

  if (loading)
    return (
      <div style={{ padding: "var(--space-8) var(--space-4)" }}>
        <p
          style={{ color: "var(--color-text-muted)" }}
          aria-live="polite"
          aria-busy="true"
        >
          Cargando batch…
        </p>
      </div>
    );

  if (batchStatus === "error")
    return (
      <div style={{ padding: "var(--space-8) var(--space-4)" }}>
        <p
          style={{
            color: "var(--color-error)",
            background: "var(--color-error-bg)",
            padding: "var(--space-3)",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--color-error)",
          }}
          role="alert"
        >
          {error || "Error desconocido en batch."}
        </p>
      </div>
    );

  const total =
    (batch?.spec as Record<string, number>)?.count ??
    (batch?.counts as Record<string, number>)?.total ??
    Math.max(progress.rendered, 1);
  const percentRendered = Math.round((progress.rendered / total) * 100);

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "var(--space-8) var(--space-4)" }}>
      {/* Progreso */}
      {batchStatus === "rendering" && (
        <section
          style={{ marginBottom: "var(--space-8)" }}
          aria-live="polite"
          aria-busy="true"
          aria-label="Progreso del batch"
        >
          <h2 style={{ margin: "0 0 var(--space-4)", fontSize: "var(--font-size-xl)", fontWeight: 700 }}>
            Renderizando batch…
          </h2>
          {/* Barra de progreso */}
          <div
            style={{
              height: "8px",
              background: "var(--color-bg)",
              borderRadius: "var(--radius-sm)",
              overflow: "hidden",
              marginBottom: "var(--space-4)",
            }}
            role="progressbar"
            aria-valuenow={percentRendered}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${percentRendered}% completado`}
          >
            <div
              style={{
                height: "100%",
                background: "var(--color-accent)",
                width: `${percentRendered}%`,
                transition: "width 0.3s ease-in-out",
              }}
            />
          </div>
          <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)", margin: 0 }}>
            {progress.rendered} / {total} renderizadas · {progress.ranked} rankeadas · {percentRendered}%
          </p>
        </section>
      )}

      {/* Grid de variaciones */}
      {batchStatus === "done" && variations.length > 0 && (
        <section>
          <h2 style={{ margin: "0 0 var(--space-6)", fontSize: "var(--font-size-xl)", fontWeight: 700 }}>
            Resultados ({variations.length} variaciones)
          </h2>
          <ul
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: "var(--space-4)",
              listStyle: "none",
              margin: 0,
              padding: 0,
            }}
            aria-label="Variaciones rankeadas del batch"
          >
            {variations.map((v) => (
              <li
                key={v.id}
                style={{
                  borderRadius: "var(--radius-md)",
                  boxShadow: "var(--shadow-md)",
                  overflow: "hidden",
                  background: "var(--color-surface)",
                }}
              >
                <div style={{ position: "relative", width: "100%", height: "200px", background: "var(--color-bg)" }}>
                  <img
                    src={downloads.fileUrl(v.id)}
                    alt=""
                    loading="lazy"
                    style={{ display: "block", width: "100%", height: "100%", objectFit: "contain" }}
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                    }}
                  />
                </div>
                <div
                  style={{
                    padding: "var(--space-3)",
                    borderTop: "1px solid var(--color-border)",
                  }}
                  aria-label={`Variación ${v.id}, score ${v.score?.toFixed(2) ?? "N/A"}`}
                >
                  <p
                    style={{
                      margin: 0,
                      fontSize: "var(--font-size-xs)",
                      color: "var(--color-text-muted)",
                    }}
                  >
                    Score: {v.score !== null ? v.score.toFixed(3) : "—"}
                  </p>
                  <button
                    onClick={() => handleDownloadVariation(v)}
                    style={{
                      marginTop: "var(--space-2)",
                      padding: "var(--space-1) var(--space-2)",
                      background: "var(--color-accent)",
                      color: "#fff",
                      border: "none",
                      borderRadius: "var(--radius-sm)",
                      fontSize: "var(--font-size-xs)",
                      fontWeight: 600,
                      cursor: "pointer",
                      width: "100%",
                    }}
                    aria-label={`Descargar variación ${v.id}`}
                  >
                    Descargar
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Acciones finales */}
      {batchStatus === "done" && (
        <div
          style={{
            marginTop: "var(--space-8)",
            display: "flex",
            gap: "var(--space-4)",
            flexWrap: "wrap",
          }}
        >
          <Link
            to="/gallery"
            style={{
              padding: "var(--space-2) var(--space-4)",
              background: "var(--color-primary)",
              color: "#fff",
              textDecoration: "none",
              borderRadius: "var(--radius-md)",
              fontWeight: 600,
              fontSize: "var(--font-size-sm)",
            }}
          >
            Ir a Galería
          </Link>
        </div>
      )}
    </div>
  );
}
