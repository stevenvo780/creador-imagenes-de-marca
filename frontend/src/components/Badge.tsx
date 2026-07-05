/**
 * Badge — indicador de estado compacto (pastilla de texto).
 * Variantes: default, success, warn, error, recommended, current
 */
import React from 'react';

export type BadgeVariant =
  | 'default'
  | 'success'
  | 'warn'
  | 'error'
  | 'recommended'
  | 'current';

export interface BadgeProps {
  label: string;
  variant?: BadgeVariant;
  style?: React.CSSProperties;
}

const variantMap: Record<BadgeVariant, React.CSSProperties> = {
  default: {
    background: 'var(--mist)',
    color: 'var(--slate-700)',
    border: '1px solid var(--line)',
  },
  success: {
    background: '#e6f9f0',
    color: '#1a7a4a',
    border: '1px solid #a7e0c4',
  },
  warn: {
    background: '#fff8e6',
    color: '#9a6800',
    border: '1px solid #f5d98a',
  },
  error: {
    background: 'var(--error-bg)',
    color: 'var(--error)',
    border: '1px solid #f5b4b0',
  },
  recommended: {
    background: 'var(--teal-600)',
    color: 'var(--white)',
    border: '1px solid var(--teal-600)',
    padding: '4px var(--space-3)',
    fontSize: 'var(--font-size-sm)',
    fontWeight: 700,
    boxShadow: 'var(--shadow-sm)',
  },
  current: {
    background: 'var(--white)',
    color: 'var(--teal-600)',
    border: '1px solid var(--teal-600)',
    padding: '4px var(--space-3)',
    fontSize: 'var(--font-size-sm)',
    fontWeight: 700,
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.22)',
  },
};

export function Badge({ label, variant = 'default', style }: BadgeProps) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px var(--space-2)',
        borderRadius: 'var(--radius-pill)',
        fontSize: 'var(--font-size-xs)',
        fontWeight: 600,
        lineHeight: 1.5,
        whiteSpace: 'nowrap',
        ...variantMap[variant],
        ...style,
      }}
    >
      {label}
    </span>
  );
}
