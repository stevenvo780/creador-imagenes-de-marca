/**
 * EmptyState — mensaje centrado cuando no hay contenido que mostrar.
 * icon: emoji o carácter decorativo (no SVG externo)
 */
import React from 'react';

export interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: string;
  action?: React.ReactNode;
}

export function EmptyState({
  title,
  description,
  icon = '🖼️',
  action,
}: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: 'var(--space-16) var(--space-4)',
        gap: 'var(--space-4)',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r-lg)',
        boxShadow: 'var(--shadow-1)',
      }}
    >
      <span
        aria-hidden="true"
        style={{ fontSize: '3rem', lineHeight: 1, opacity: 0.7 }}
      >
        {icon}
      </span>

      <div style={{ display: 'grid', gap: 'var(--space-2)' }}>
        <h3
          style={{
            margin: 0,
            fontFamily: 'var(--font-display)',
            fontSize: 'var(--font-size-xl)',
            color: 'var(--text)',
          }}
        >
          {title}
        </h3>
        {description && (
          <p
            style={{
              margin: 0,
              fontSize: 'var(--font-size-sm)',
              color: 'var(--text-muted)',
              maxWidth: '40ch',
              marginInline: 'auto',
            }}
          >
            {description}
          </p>
        )}
      </div>

      {action && <div>{action}</div>}
    </div>
  );
}
