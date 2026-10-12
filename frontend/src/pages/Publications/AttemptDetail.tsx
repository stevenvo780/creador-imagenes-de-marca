import { Attempt, Delivery, safePermalink } from "../../api/publications";
export const states: Record<string, string> = {
  scheduled: "Programada",
  held: "Retenida",
  reserved: "Reservada",
  attempt_started: "Intento iniciado",
  published: "Publicada",
  withdrawn: "Retirada",
  failed: "Fallida",
  uncertain: "Resultado incierto",
  expired: "Fecha expirada",
  cancelled: "Cancelada antes del intento",
};
export function AttemptDetail({ attempt }: { attempt: Attempt | Delivery }) {
  const href =
    attempt.state === "published" && attempt.result?.state === "published"
      ? safePermalink(attempt.result.permalink)
      : null;
  return (
    <div className="pub-attempt">
      <strong>
        {attempt.state === "published" && attempt.visibility === "private"
          ? "Publicada en privado (sólo yo)"
          : states[attempt.state] || "Estado pendiente"}
      </strong>
      {attempt.state === "uncertain" && (
        <p>
          Se necesita conciliar el resultado. No se repetirá el envío
          automáticamente.
        </p>
      )}
      {attempt.state === "expired" && (
        <p>
          Prepara una nueva revisión con otra fecha y una nueva evaluación IA.
        </p>
      )}
      {href && (
        <a href={href} target="_blank" rel="noopener noreferrer">
          Ver publicación
        </a>
      )}
      {attempt.state === "published" && attempt.result?.remote_id && (
        <p>Recibo: {attempt.result.remote_id}</p>
      )}
      {"events" in attempt && attempt.events && (
        <ol>
          {attempt.events.map((e) => (
            <li key={e.id}>
              {states[e.kind] || e.kind} —{" "}
              {new Date(e.created_at * 1000).toLocaleString()}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
