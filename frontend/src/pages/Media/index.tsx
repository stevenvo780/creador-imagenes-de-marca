import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { brands, type Brand } from "../../api/client";
import {
  listMedia,
  listProjects,
  mediaError,
  isAbort,
  type Media,
  type MediaFilters,
  type Project,
} from "../../api/media";
import { Button } from "../../components";
import { GalleryPage as LegacyGallery } from "../Gallery";
import { MediaCard } from "./MediaCard";
import { MediaDetail } from "./MediaDetail";
export function MediaGallery({ owner }: { owner: boolean }) {
  const [params] = useSearchParams();
  const [legacy, setLegacy] = useState(params.has("batch"));
  const [items, setItems] = useState<Media[]>([]),
    [brandList, setBrands] = useState<Brand[]>([]),
    [projects, setProjects] = useState<Project[]>([]),
    [filters, setFilters] = useState<MediaFilters>({
      project_id: params.get("project")
        ? Number(params.get("project"))
        : undefined,
    }),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [selected, setSelected] = useState<number | null>(null),
    [refresh, setRefresh] = useState(0),
    [next, setNext] = useState<number | null>(null),
    [moreBusy, setMoreBusy] = useState(false);
  const queryKey = JSON.stringify([filters, refresh, legacy]);
  const queryKeyRef = useRef(queryKey);
  queryKeyRef.current = queryKey;
  const query = useRef<{ controller: AbortController; key: string } | null>(
    null,
  );

  useEffect(() => {
    let active = true;
    void brands
      .list()
      .then((r) => {
        if (active) setBrands(r.items);
      })
      .catch(() => {});
    const c = new AbortController();
    async function allProjects() {
      let cursor: number | undefined;
      const list: Project[] = [];
      do {
        const r = await listProjects(c.signal, cursor);
        list.push(...r.items);
        cursor = r.next_cursor ?? undefined;
      } while (cursor !== undefined);
      if (!c.signal.aborted) setProjects(list);
    }
    void allProjects().catch((e) => {
      if (!isAbort(e)) setError(mediaError(e));
    });
    return () => {
      active = false;
      c.abort();
    };
  }, []);
  useEffect(() => {
    query.current?.controller.abort();
    const current = { controller: new AbortController(), key: queryKey };
    query.current = current;
    setNext(null);
    setMoreBusy(false);
    setLoading(!legacy);
    setItems([]);
    setError("");
    if (!legacy)
      void listMedia(filters, current.controller.signal)
        .then((r) => {
          if (
            queryKeyRef.current !== current.key ||
            query.current !== current ||
            current.controller.signal.aborted
          )
            return;
          setItems(r.items);
          setNext(r.next_cursor);
        })
        .catch((e) => {
          if (
            queryKeyRef.current === current.key &&
            query.current === current &&
            !current.controller.signal.aborted &&
            !isAbort(e)
          )
            setError(mediaError(e));
        })
        .finally(() => {
          if (
            queryKeyRef.current === current.key &&
            query.current === current &&
            !current.controller.signal.aborted
          )
            setLoading(false);
        });
    return () => current.controller.abort();
  }, [filters, refresh, legacy]);
  async function more() {
    const current = query.current;
    if (
      next === null ||
      !current ||
      queryKeyRef.current !== current.key ||
      current.controller.signal.aborted ||
      moreBusy
    )
      return;
    setMoreBusy(true);
    try {
      const r = await listMedia(
        { ...filters, cursor: next },
        current.controller.signal,
      );
      if (
        queryKeyRef.current !== current.key ||
        query.current !== current ||
        current.controller.signal.aborted
      )
        return;
      setItems((i) => [...i, ...r.items]);
      setNext(r.next_cursor);
    } catch (e) {
      if (
        queryKeyRef.current === current.key &&
        query.current === current &&
        !current.controller.signal.aborted &&
        !isAbort(e)
      )
        setError(mediaError(e));
    } finally {
      if (
        queryKeyRef.current === current.key &&
        query.current === current &&
        !current.controller.signal.aborted
      )
        setMoreBusy(false);
    }
  }

  return (
    <section className="media-page">
      <div
        className="media-view-switch"
        role="group"
        aria-label="Vista de galería"
      >
        <Button
          variant={legacy ? "secondary" : "primary"}
          onClick={() => setLegacy(false)}
        >
          Imágenes para revisión
        </Button>
        <Button
          variant={legacy ? "primary" : "secondary"}
          onClick={() => setLegacy(true)}
        >
          Variaciones del generador
        </Button>
      </div>
      {legacy ? (
        <LegacyGallery />
      ) : (
        <>
          <div className="media-heading">
            <div>
              <h1>Galería</h1>
              <p>
                Revisá el original, su identidad y su historial antes de
                aprobar.
              </p>
            </div>
            <Button
              variant="secondary"
              onClick={() => setRefresh((v) => v + 1)}
            >
              Actualizar galería
            </Button>
          </div>
          <div className="media-filters">
            <label>
              Marca
              <select
                value={filters.brand_id ?? ""}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    brand_id: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  }))
                }
              >
                <option value="">Todas las marcas</option>
                {brandList.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Proyecto
              <select
                value={filters.project_id ?? ""}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    project_id: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  }))
                }
              >
                <option value="">Todos los proyectos</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Origen
              <select
                value={filters.source ?? ""}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    source: (e.target.value ||
                      undefined) as MediaFilters["source"],
                  }))
                }
              >
                <option value="">Todos los orígenes</option>
                <option value="codex">Codex</option>
                <option value="legacy">Generador Eikón</option>
              </select>
            </label>
            <label>
              Estado
              <select
                value={filters.status ?? ""}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    status: (e.target.value ||
                      undefined) as MediaFilters["status"],
                  }))
                }
              >
                <option value="">Todos los estados</option>
                <option value="pending_review">Pendiente de revisión</option>
                <option value="approved">Aprobado</option>
                <option value="rejected">Rechazado</option>
                <option value="archived">Archivado</option>
              </select>
            </label>
          </div>
          {error && (
            <div role="alert">
              <p>{error}</p>
              <Button
                variant="secondary"
                onClick={() => setRefresh((v) => v + 1)}
              >
                Reintentar
              </Button>
            </div>
          )}
          {loading || query.current?.key !== queryKey ? (
            <p role="status">Cargando imágenes…</p>
          ) : !error && items.length === 0 ? (
            <div className="media-empty">
              <h2>No hay imágenes con estos filtros</h2>
              <p>
                Probá otro estado o incorporá una pieza de Codex o del
                generador.
              </p>
              <Button variant="secondary" onClick={() => setFilters({})}>
                Limpiar filtros
              </Button>
            </div>
          ) : (
            <div className="media-grid">
              {items.map((item) => (
                <MediaCard
                  key={item.id}
                  item={item}
                  brandName={
                    brandList.find((b) => b.id === item.brand_id)?.name ??
                    `Marca ${item.brand_id}`
                  }
                  projectName={
                    projects.find((p) => p.id === item.project_id)?.name ??
                    `Proyecto ${item.project_id}`
                  }
                  onOpen={() => setSelected(item.id)}
                />
              ))}
            </div>
          )}
          {next !== null && !loading && query.current?.key === queryKey && (
            <Button
              variant="secondary"
              busy={moreBusy}
              onClick={() => void more()}
            >
              Cargar más imágenes
            </Button>
          )}
          {selected !== null && (
            <MediaDetail
              key={selected}
              id={selected}
              owner={owner}
              onClose={() => setSelected(null)}
              onReviewed={() => setRefresh((v) => v + 1)}
            />
          )}
        </>
      )}
    </section>
  );
}
