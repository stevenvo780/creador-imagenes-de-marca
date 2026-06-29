/**
 * Badge — indicador de estado compacto (pastilla de texto).
 * Variantes: default, success, warn, error, recommended
 */
import React from 'react';

export interface BadgeProps {
  label: string;
  variant?: 'default' | 'success' | 'warn' | 'error' | 'recommended';
  style?: React.CSSProperties;
}

const variantMap: Record<
  NonNullable<BadgeProps['variant']>,
  React.CSSProperties
> = {
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
    background: '#edf7f6',
    color: 'var(--teal-600)',
    border: '1px solid var(--teal)',
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
