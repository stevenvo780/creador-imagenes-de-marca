/**
 * Stars — muestra la calidad de una variación.
 * score 0–1 → 1–5 estrellas (o badge "Recomendado" si score >= 0.9).
 * NO muestra el número crudo de score al usuario.
 */
import { Badge } from './Badge';

export interface StarsProps {
  /** Puntuación entre 0 y 1. null = sin datos. */
  score: number | null;
  /** Mostrar siempre como estrellas aunque sea recomendado. */
  forceStars?: boolean;
}

const RECOMMENDED_THRESHOLD = 0.9;

function scoreToStars(score: number): number {
  // 0–1 → 1–5 estrellas (redondeo a entero)
  return Math.max(1, Math.min(5, Math.round(score * 5)));
}

export function Stars({ score, forceStars = false }: StarsProps) {
  if (score === null) {
    return (
      <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--slate-500)' }}>
        Sin calificar
      </span>
    );
  }

  if (score >= RECOMMENDED_THRESHOLD && !forceStars) {
    return <Badge label="Recomendado" variant="recommended" />;
  }

  const filled = scoreToStars(score);

  return (
    <span
      role="img"
      aria-label={`Calidad: ${filled} de 5 estrellas`}
      style={{ display: 'inline-flex', gap: '1px', lineHeight: 1 }}
    >
      {Array.from({ length: 5 }, (_, i) => (
        <span
          key={i}
          style={{
            fontSize: 'var(--font-size-sm)',
            // gold-dark = 4.7:1 sobre blanco (AA para objeto gráfico)
            color: i < filled ? 'var(--gold-dark)' : 'var(--line)',
          }}
          aria-hidden="true"
        >
          ★
        </span>
      ))}
    </span>
  );
}
