/**
 * Spinner — indicador de carga circular animado.
 * La animación se desactiva automáticamente si el usuario
 * prefiere movimiento reducido (CSS: prefers-reduced-motion).
 */
import React from 'react';

export interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
  style?: React.CSSProperties;
}

const sizeMap: Record<NonNullable<SpinnerProps['size']>, number> = {
  sm: 16,
  md: 24,
  lg: 40,
};

export function Spinner({
  size = 'md',
  label = 'Cargando…',
  style,
}: SpinnerProps) {
  const px = sizeMap[size];
  const stroke = size === 'sm' ? 2 : 3;

  return (
    <span
      role="status"
      aria-label={label}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        ...style,
      }}
    >
      <svg
        aria-hidden="true"
        width={px}
        height={px}
        viewBox="0 0 24 24"
        fill="none"
        style={{
          animation: 'eikon-spin 0.8s linear infinite',
        }}
      >
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke="var(--border)"
          strokeWidth={stroke}
        />
        <path
          d="M12 2 a10 10 0 0 1 10 10"
          stroke="var(--teal)"
          strokeWidth={stroke}
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}
