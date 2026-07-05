/**
 * SelectField — <select> estilizado con label + hint + error.
 * Para un select sin label usa un <select> con aria-label directamente.
 */
import React from 'react';

export interface SelectFieldProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  id: string;
  label: string;
  hint?: string;
  error?: string;
}

export function SelectField({
  id,
  label,
  hint,
  error,
  style,
  children,
  ...props
}: SelectFieldProps) {
  const hintId  = hint  ? `${id}-hint`  : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy =
    [hintId, errorId].filter(Boolean).join(' ') || undefined;

  const selectStyle: React.CSSProperties = {
    display: 'block',
    width: '100%',
    padding: 'var(--space-2) var(--space-3)',
    fontFamily: 'var(--font-body)',
    fontSize: 'var(--font-size-base)',
    color: 'var(--text)',
    background: 'var(--surface-2)',
    border: error ? '1.5px solid var(--danger)' : '1.5px solid var(--border)',
    borderRadius: 'var(--r-md)',
    cursor: 'pointer',
    appearance: 'auto',
    outline: 'none',
    transition: 'border-color var(--transition-fast)',
    boxSizing: 'border-box',
    ...style,
  };

  return (
    <div style={{ display: 'grid', gap: 'var(--space-1)' }}>
      <label
        htmlFor={id}
        style={{
          display: 'block',
          fontSize: 'var(--font-size-sm)',
          fontWeight: 600,
          color: 'var(--text)',
        }}
      >
        {label}
      </label>

      <select
        id={id}
        aria-describedby={describedBy}
        aria-invalid={error ? 'true' : undefined}
        style={selectStyle}
        {...props}
      >
        {children}
      </select>

      {hint && !error && (
        <p id={hintId} style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" style={{ margin: 0, fontSize: 'var(--font-size-xs)', color: 'var(--danger)', fontWeight: 500 }}>
          {error}
        </p>
      )}
    </div>
  );
}
