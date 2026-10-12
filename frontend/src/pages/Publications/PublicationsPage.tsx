import { Button } from "../../components";
import { useEffect, useState, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Overview,
  getOverview,
  getCampaigns,
  errorMessage,
  isAbort,
} from "../../api/publications";
import { PolicyPanel } from "./PolicyPanel";
import { CampaignDetail } from "./CampaignDetail";
import { CalendarPanel } from "./CalendarPanel";
import { ConnectionPanel } from "./ConnectionPanel";
import "./publications.css";
export function PublicationsPage({
  owner,
  tenant,
}: {
  owner: boolean;
  tenant: string;
}) {
  const { campaignId } = useParams(),
    [data, setData] = useState<Overview | null>(null),
    [error, setError] = useState(""),
    [version, setVersion] = useState(0),
    [busy, setBusy] = useState(false);
  const operation = useRef(new AbortController());
  useEffect(() => {
    operation.current.abort();
    const c = new AbortController();
    operation.current = c;
    setBusy(false);
    setData(null);
    setError("");
    if (!owner) return () => c.abort();
    getOverview(c.signal)
      .then(setData)
      .catch((e) => {
        if (!isAbort(e)) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [owner, tenant, version]);
  const more = async () => {
    if (!data?.campaigns.next_cursor) return;
    setBusy(true);
    try {
      const p = await getCampaigns(
        data.campaigns.next_cursor,
        operation.current.signal,
      );
      setData({
        ...data,
        campaigns: { ...p, items: [...data.campaigns.items, ...p.items] },
      });
    } catch (e) {
      if (!isAbort(e)) setError(errorMessage(e));
    } finally {
      if (!operation.current.signal.aborted) setBusy(false);
    }
  };
  const selected = data?.campaigns.items.find(
    (c) => String(c.id) === campaignId,
  );
  return (
    <div className="publications">
      <header className="pub-heading">
        <h1>Publicaciones</h1>
        <p className="pub-tenant">
          Empresa activa: <strong>{tenant}</strong>
        </p>
        <p>
          Del producto al recibo: piezas, decisiones IA y envíos por cuenta.
        </p>
      </header>
      {!owner && (
        <p role="status">
          Sólo el owner de esta empresa puede consultar y administrar
          publicaciones.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {owner && !data && !error && <p role="status">Cargando publicaciones…</p>}
      {data && (
        <>
          <PolicyPanel
            key={`policy:${data.policy.version}`}
            policy={data.policy}
            owner={owner}
            onRefresh={() => setVersion((v) => v + 1)}
          />
          <div className="pub-workspace">
            <aside>
              <h2>Productos y campañas</h2>
              {!data.campaigns.items.length && (
                <p>
                  No hay campañas. Crea un proyecto y prepara una campaña con el
                  cliente Codex de esta empresa.
                </p>
              )}
              <ul>
                {data.campaigns.items.map((c) => (
                  <li key={c.id}>
                    <Link
                      aria-current={
                        String(c.id) === campaignId ? "page" : undefined
                      }
                      to={`/publications/campaigns/${c.id}`}
                    >
                      {c.product_name}: {c.objective}
                    </Link>
                    <p>{c.project_name}</p>
                  </li>
                ))}
              </ul>
              {data.campaigns.next_cursor !== null && (
                <Button disabled={busy} onClick={more}>
                  Cargar más campañas
                </Button>
              )}
            </aside>
            <div>
              {selected ? (
                <CampaignDetail
                  key={selected.id}
                  campaign={selected}
                  policyVersion={data.policy.version}
                  owner={owner}
                  onRefresh={() => setVersion((v) => v + 1)}
                />
              ) : (
                <p>
                  {campaignId
                    ? "La campaña no está en esta página. Carga más campañas o selecciona una de la lista."
                    : "Selecciona una campaña para revisar sus piezas y decisiones."}
                </p>
              )}
            </div>
          </div>
          <CalendarPanel key={`calendar:${version}`} owner={owner} />
          <ConnectionPanel
            connections={data.connections}
            onRefresh={() => setVersion((v) => v + 1)}
          />
        </>
      )}
    </div>
  );
}
