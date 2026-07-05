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
    background: 'var(--surface-2)',
    color: 'var(--text-muted)',
    border: '1px solid var(--border)',
  },
  success: {
    background: 'color-mix(in srgb, var(--ok) 16%, transparent)',
    color: 'var(--ok)',
    border: '1px solid color-mix(in srgb, var(--ok) 42%, var(--border))',
  },
  warn: {
    background: 'color-mix(in srgb, var(--amber) 15%, transparent)',
    color: 'var(--amber)',
    border: '1px solid color-mix(in srgb, var(--amber) 42%, var(--border))',
  },
  error: {
    background: 'var(--error-bg)',
    color: 'var(--danger)',
    border: '1px solid color-mix(in srgb, var(--danger) 42%, var(--border))',
  },
  recommended: {
    background: 'var(--amber)',
    color: 'var(--teal-ink)',
    border: '1px solid var(--amber)',
    padding: '4px var(--space-3)',
    fontSize: 'var(--font-size-sm)',
    fontWeight: 700,
    boxShadow: 'var(--shadow-sm)',
  },
  current: {
    background: 'var(--teal)',
    color: 'var(--teal-ink)',
    border: '1px solid var(--teal)',
    padding: '4px var(--space-3)',
    fontSize: 'var(--font-size-sm)',
    fontWeight: 700,
    boxShadow: 'var(--shadow-2)',
  },
};

export function Badge({ label, variant = 'default', style }: BadgeProps) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px var(--space-2)',
        borderRadius: 'var(--r-md)',
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
