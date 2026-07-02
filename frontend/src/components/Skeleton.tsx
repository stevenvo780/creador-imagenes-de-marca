/**
 * Skeleton — placeholder animado mientras carga el contenido.
 * Usa la animación eikon-pulse definida en theme.css.
 */
import React from 'react';

export interface SkeletonProps {
  width?: string;
  height?: string;
  borderRadius?: string;
  style?: React.CSSProperties;
}

export function Skeleton({
  width = '100%',
  height = '1rem',
  borderRadius = 'var(--radius-sm)',
  style,
}: SkeletonProps) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'block',
        width,
        height,
        borderRadius,
        background: 'var(--mist)',
        animation: 'eikon-pulse 1.4s ease-in-out infinite',
        ...style,
      }}
    />
  );
}

/** Grupo de skeletons para una tarjeta típica */
export function SkeletonCard() {
  return (
    <div
      style={{
        padding: 'var(--space-4)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--radius-lg)',
        display: 'grid',
        gap: 'var(--space-3)',
      }}
    >
      <Skeleton height="180px" borderRadius="var(--radius-md)" />
      <Skeleton width="60%" height="var(--font-size-sm)" />
      <Skeleton width="40%" height="var(--font-size-xs)" />
    </div>
  );
}
