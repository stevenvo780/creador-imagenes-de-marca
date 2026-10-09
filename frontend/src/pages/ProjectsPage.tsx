import { usePrivateOperation } from "./Media/usePrivateOperation";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  listProjects,
  createProject,
  mediaError,
  isAbort,
  type Project,
} from "../api/media";
import { Button, Modal } from "../components";
export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [open, setOpen] = useState(false),
    [name, setName] = useState(""),
    [slug, setSlug] = useState(""),
    [description, setDescription] = useState(""),
    [busy, setBusy] = useState(false),
    [retry, setRetry] = useState(0),
    [next, setNext] = useState<number | null>(null);
  const controller = usePrivateOperation();

  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    setError("");
    void listProjects(c.signal)
      .then((r) => {
        setProjects(r.items);
        setNext(r.next_cursor);
      })
      .catch((e) => {
        if (!isAbort(e)) setError(mediaError(e));
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [retry]);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const p = await createProject(
        { name: name.trim(), slug, description: description.trim() },
        controller.current.signal,
      );
      if (controller.current.signal.aborted) return;
      setProjects((ps) => [...ps, p]);
      setOpen(false);
      setName("");
      setSlug("");
      setDescription("");
    } catch (e) {
      if (!isAbort(e)) setError(mediaError(e));
    } finally {
      if (!controller.current.signal.aborted) setBusy(false);
    }
  }
  async function more() {
    if (next === null) return;
    setBusy(true);
    try {
      const r = await listProjects(controller.current.signal, next);
      setProjects((ps) => [...ps, ...r.items]);
      setNext(r.next_cursor);
    } catch (e) {
      if (!isAbort(e)) setError(mediaError(e));
    } finally {
      if (!controller.current.signal.aborted) setBusy(false);
    }
  }
  return (
    <section className="media-page">
      <div className="media-heading">
        <div>
          <h1>Proyectos</h1>
          <p>Organizá las marcas y piezas de cada campaña.</p>
        </div>
        <Button onClick={() => setOpen(true)}>Nuevo proyecto</Button>
      </div>
      {error && (
        <div role="alert">
          <p>{error}</p>
          <Button variant="secondary" onClick={() => setRetry((v) => v + 1)}>
            Reintentar
          </Button>
        </div>
      )}
      {loading ? (
        <p role="status">Cargando proyectos…</p>
      ) : projects.length === 0 ? (
        <p>Creá tu primer proyecto para organizar las piezas.</p>
      ) : (
        <ul className="media-projects">
          {projects.map((p) => (
            <li key={p.id}>
              <h2>{p.name}</h2>
              <p>{p.description || "Sin descripción"}</p>
              <Link to={`/gallery?project=${p.id}`}>
                Ver piezas del proyecto
              </Link>
            </li>
          ))}
        </ul>
      )}
      {next !== null && (
        <Button variant="secondary" busy={busy} onClick={() => void more()}>
          Cargar más proyectos
        </Button>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Nuevo proyecto">
        <form className="media-form" onSubmit={(e) => void save(e)}>
          <label>
            Nombre del proyecto
            <input
              required
              maxLength={120}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setSlug(
                  e.target.value
                    .normalize("NFD")
                    .replace(/[\u0300-\u036f]/g, "")
                    .toLowerCase()
                    .replace(/[^a-z0-9]+/g, "-")
                    .replace(/^-|-$/g, ""),
                );
              }}
            />
          </label>
          <label>
            Identificador
            <input
              required
              maxLength={80}
              pattern="[a-z0-9][a-z0-9-]*"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
            />
          </label>
          <label>
            Descripción
            <textarea
              maxLength={4000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          {error && <p role="alert">{error}</p>}
          <Button type="submit" busy={busy}>
            Guardar
          </Button>
        </form>
      </Modal>
    </section>
  );
}
