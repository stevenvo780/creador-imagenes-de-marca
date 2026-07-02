/**
 * PageHeader — cabecera de sección con título, subtítulo opcional
 * y una acción (botón, enlace) a la derecha.
 */
import React from 'react';

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 'var(--space-4)',
        marginBottom: 'var(--space-6)',
        flexWrap: 'wrap',
      }}
    >
      <div style={{ display: 'grid', gap: 'var(--space-1)' }}>
        <h1
          style={{
            margin: 0,
            fontFamily: 'var(--font-display)',
            fontSize: 'var(--font-size-2xl)',
            fontWeight: 700,
            color: 'var(--ink)',
            lineHeight: 1.2,
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <p
            style={{
              margin: 0,
              fontSize: 'var(--font-size-sm)',
              color: 'var(--slate-500)',
            }}
          >
            {subtitle}
          </p>
        )}
      </div>

      {action && (
        <div style={{ flexShrink: 0, marginTop: 'var(--space-1)' }}>
          {action}
        </div>
      )}
    </div>
  );
}
