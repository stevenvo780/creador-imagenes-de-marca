import { Button } from "../../components";
import { useEffect, useState, useRef } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Overview, getOverview, getCampaigns, errorMessage, isAbort } from "../../api/publications";
import { PolicyPanel, policyStatus } from "./PolicyPanel";
import { CampaignDetail } from "./CampaignDetail";
import { CalendarPanel } from "./CalendarPanel";
import { ConnectionPanel } from "./ConnectionPanel";
import "./publications.css";

type View = "agenda" | "content" | "accounts";
export function PublicationsPage({ owner, tenant }: { owner: boolean; tenant: string }) {
  const { campaignId } = useParams();
  const navigate = useNavigate();
  const [loaded, setLoaded] = useState<{ tenant: string; version: number; overview: Overview } | null>(null);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState<View>(campaignId ? "content" : "agenda");
  const [query, setQuery] = useState("");
  const operation = useRef(new AbortController());
  const data = owner && loaded?.tenant === tenant && loaded.version === version ? loaded.overview : null;
  useEffect(() => { setView(campaignId ? "content" : "agenda"); }, [campaignId, tenant]);
  useEffect(() => { setQuery(""); }, [tenant]);
  useEffect(() => {
    operation.current.abort();
    const c = new AbortController();
    operation.current = c;
    setBusy(false); setLoaded(null); setError("");
    if (!owner) return () => c.abort();
    getOverview(c.signal).then(overview => {
      if (!c.signal.aborted) setLoaded({ tenant, version, overview });
    }).catch(e => { if (!isAbort(e) && !c.signal.aborted) setError(errorMessage(e)); });
    return () => c.abort();
  }, [owner, tenant, version]);
  const refresh = () => setVersion(v => v + 1);
  const more = async () => {
    if (!data || data.campaigns.next_cursor === null) return;
    const c = operation.current;
    setBusy(true);
    try {
      const p = await getCampaigns(data.campaigns.next_cursor, c.signal);
      if (!c.signal.aborted) setLoaded({ tenant, version, overview: {
        ...data, campaigns: { ...p, items: [...data.campaigns.items, ...p.items] },
      } });
    } catch (e) { if (!isAbort(e) && !c.signal.aborted) setError(errorMessage(e)); }
    finally { if (!c.signal.aborted) setBusy(false); }
  };
  const selectView = (next: View) => {
    setView(next);
    if (next === "agenda" && campaignId) navigate("/publications");
  };
  const selected = data?.campaigns.items.find(c => String(c.id) === campaignId);
  const search = query.trim().toLocaleLowerCase("es");
  const campaigns = data?.campaigns.items.filter(c =>
    `${c.product_name} ${c.project_name} ${c.objective}`.toLocaleLowerCase("es").includes(search)) || [];
  const connected = data?.connections.filter(c => c.status === "active" &&
    (!c.expires_at || c.expires_at > Date.now() / 1000)).length || 0;
  return (
    <div className="publications">
      <header className="pub-heading">
        <div>
          <h1>Publicaciones</h1>
          <p className="pub-tenant">Empresa activa: <strong>{tenant}</strong></p>
          <p>Organiza el contenido y sigue cada envío a las redes de tu empresa.</p>
        </div>
        {owner && <Button variant="secondary" disabled={!data && !error} onClick={refresh}>Actualizar</Button>}
      </header>
      {!owner && <p role="status">Sólo el owner de esta empresa puede consultar y administrar publicaciones.</p>}
      {error && <p role="alert">{error}</p>}
      {owner && !data && !error && <p role="status">Cargando publicaciones…</p>}
      {data && <>
        <nav className="pub-views" aria-label="Vistas de publicaciones">
          {([["agenda", "Agenda"], ["content", "Contenido"], ["accounts", "Cuentas"]] as const).map(([id, label]) =>
            <button key={id} type="button" aria-pressed={view === id} onClick={() => selectView(id)}>{label}</button>)}
        </nav>
        <div className="pub-context">
          <span>{connected} {connected === 1 ? "cuenta conectada" : "cuentas conectadas"}</span>
          <span>Autorización: {policyStatus(data.policy)}</span>
          <span>La conexión no confirma una publicación.</span>
        </div>
        <div className="pub-workspace">
          <aside className="pub-products" aria-labelledby="products-heading">
            <h2 id="products-heading">Productos y campañas</h2>
            <label className="pub-search">Buscar producto o campaña
              <input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Nombre, proyecto u objetivo" />
            </label>
            <p className="pub-list-meta">{campaigns.length} de {data.campaigns.items.length} campañas cargadas{data.campaigns.next_cursor !== null ? " · Lista parcial" : ""}</p>
            {!data.campaigns.items.length && <p>No hay campañas. Prepara una desde un proyecto con el cliente Codex de esta empresa.</p>}
            {!!data.campaigns.items.length && !campaigns.length && <p role="status">No hay coincidencias. Prueba otro nombre o carga más campañas.</p>}
            <ul className="pub-product-list">
              {campaigns.map(c => <li key={c.id}>
                <Link aria-current={String(c.id) === campaignId && view === "content" ? "page" : undefined}
                  to={`/publications/campaigns/${c.id}`} onClick={() => setView("content")}>
                  <strong>{c.product_name}</strong>
                  <span>{c.project_name}</span>
                  <small>Campaña {c.id} · {c.revisions.length} revisiones{c.archived ? " · Archivada" : ""}</small>
                </Link>
              </li>)}
            </ul>
            {data.campaigns.next_cursor !== null && <Button variant="secondary" disabled={busy} onClick={more}>Cargar más campañas</Button>}
          </aside>
          <div className="pub-main">
            {view === "agenda" && <CalendarPanel key={`calendar:${tenant}:${version}`} owner={owner} onContent={() => selectView("content")} />}
            {view === "content" && (selected ?
              <CampaignDetail key={`${tenant}:${selected.id}`} campaign={selected} policyVersion={data.policy.version} owner={owner} onRefresh={refresh} /> :
              <section className="pub-content-intro">
                <h2>Contenido por producto</h2>
                <p>{campaignId ? "La campaña no está en esta página. Carga más campañas o selecciona una de la lista." : "Selecciona un producto para consultar su objetivo completo, las piezas y sus decisiones IA."}</p>
                <p>La galería conserva tus piezas; aquí sigues las revisiones preparadas para cada cuenta.</p>
                <Link to="/projects">Ir a proyectos</Link>
              </section>)}
            {view === "accounts" && <ConnectionPanel key={`accounts:${tenant}`} connections={data.connections} onRefresh={refresh} />}
          </div>
        </div>
        <PolicyPanel key={`policy:${tenant}:${data.policy.version}`} policy={data.policy} owner={owner} onRefresh={refresh} />
      </>}
    </div>
  );
}
