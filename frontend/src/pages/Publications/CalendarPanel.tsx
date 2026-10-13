import { Button } from "../../components";
import { useEffect, useState } from "react";
import {
  Delivery,
  getCalendar,
  getDelivery,
  isAbort,
  errorMessage,
  publicationRequest,
} from "../../api/publications";
import { AttemptDetail } from "./AttemptDetail";
import { usePrivateOperation } from "../Media/usePrivateOperation";
export function CalendarPanel({ owner, onContent }: { owner: boolean; onContent?: () => void }) {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<Delivery[]>([]),
    [cursor, setCursor] = useState<number | null>(0),
    [error, setError] = useState(""),
    [selected, setSelected] = useState<Delivery | null>(null),
    [busy, setBusy] = useState(false);
  const operation = usePrivateOperation();
  useEffect(() => {
    const c = new AbortController();
    if (!owner) { setLoading(false); return () => c.abort(); }
    getCalendar(0, c.signal)
      .then((p) => {
        if (c.signal.aborted) return;
        setItems(p.items);
        setCursor(p.next_cursor);
      })
      .catch((e) => {
        if (!isAbort(e) && !c.signal.aborted) setError(errorMessage(e));
      }).finally(() => { if (!c.signal.aborted) setLoading(false); });
    return () => c.abort();
  }, []);
  const more = async () => {
    if (cursor === null) return;
    setBusy(true);
    try {
      const p = await getCalendar(cursor, operation.current.signal);
      setItems((old) => [...old, ...p.items]);
      setCursor(p.next_cursor);
    } catch (e) {
      if (!isAbort(e)) setError(errorMessage(e));
    } finally {
      if (!operation.current.signal.aborted) setBusy(false);
    }
  };
  const inspect = async (id: number) => {
    setSelected(null);
    setBusy(true);
    try {
      setSelected(await getDelivery(id, operation.current.signal));
    } catch (e) {
      if (!isAbort(e)) setError(errorMessage(e));
    } finally {
      if (!operation.current.signal.aborted) setBusy(false);
    }
  };
  const cancel = async (d: Delivery) => {
    setBusy(true);
    try {
      await publicationRequest(
        `/calendar/deliveries/${d.id}/cancel`,
        "POST",
        {},
        operation.current.signal,
      );
      setSelected(null);
      const p = await getCalendar(0, operation.current.signal);
      setItems(p.items);
      setCursor(p.next_cursor);
    } catch (e) {
      if (!isAbort(e)) setError(errorMessage(e));
    } finally {
      if (!operation.current.signal.aborted) setBusy(false);
    }
  };
  return (
    <section className="pub-calendar" aria-labelledby="calendar-heading">
      <header className="pub-section-heading">
        <h2 id="calendar-heading">Agenda de envíos</h2>
        <p>Fechas, requisitos y recibos por cuenta.</p>
      </header>
      {loading && <p role="status">Cargando agenda…</p>}
      {!loading && !error && !!items.length && <p className="pub-list-meta">{items.length} entregas cargadas{cursor !== null ? " · Lista parcial" : ""}. Sólo un recibo confirmado acredita la publicación.</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && !items.length && <div className="pub-empty-agenda">
        <h3>Aún no hay entregas programadas</h3>
        <p>Revisa el contenido de un producto. Una decisión IA vigente y los requisitos de la cuenta permiten programar su envío.</p>
        {onContent && <Button onClick={onContent}>Ir a Contenido</Button>}
      </div>}
      <ol className="pub-agenda">
        {items.map((d) => (
          <li key={d.id}>
            <div className="pub-delivery-date">
              <strong>{d.normalized_destination}</strong>
              <p>
                <time dateTime={new Date(d.due_at * 1000).toISOString()}>
                  {new Date(d.due_at * 1000).toLocaleString()}
                </time>{" "}
                ({Intl.DateTimeFormat().resolvedOptions().timeZone})
              </p>
            </div>
            <div className="pub-delivery-result">
            <AttemptDetail
              attempt={{
                ...d,
                state:
                  !d.started_at &&
                  ["scheduled", "held"].includes(d.state) &&
                  d.expires_at <= Date.now() / 1000
                    ? "expired"
                    : d.state,
              }}
            />
            {d.hold_reasons.map((r) => (
              <p key={r}>{r}</p>
            ))}
            {d.state === "held" && (
              <p>
                Tras una retención del trabajador se requiere una nueva revisión
                y decisión IA.
              </p>
            )}
            </div>
            <div className="pub-delivery-actions">
            <Button variant="secondary" disabled={busy} onClick={() => inspect(d.id)}>
              Ver intento y recibo
            </Button>
            {owner &&
              !d.started_at &&
              ["scheduled", "held", "reserved"].includes(d.state) && (
                <Button disabled={busy} onClick={() => cancel(d)}>
                  Cancelar antes del intento
                </Button>
              )}
            </div>
          </li>
        ))}
      </ol>
      {!loading && cursor !== null && (
        <Button disabled={busy} onClick={more}>
          Cargar más entregas
        </Button>
      )}
      {selected && (
        <aside aria-label="Detalle de entrega">
          <h3>Entrega {selected.id}</h3>
          <AttemptDetail attempt={selected} />
        </aside>
      )}
    </section>
  );
}
