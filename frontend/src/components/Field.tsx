/**
 * Field — envuelve un control (Input, Select, etc.) con label, hint y error.
 * Uso:
 *   <Field id="email" label="Correo" hint="Ej: usuario@mail.com" error={errMsg}>
 *     <Input id="email" type="email" />
 *   </Field>
 */
import React from 'react';

export interface FieldProps {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: React.ReactNode;
}

export function Field({ id, label, hint, error, required = false, children }: FieldProps) {
  const hintId  = hint  ? `${id}-hint`  : undefined;
  const errorId = error ? `${id}-error` : undefined;

  return (
    <div style={{ display: 'grid', gap: 'var(--space-1)' }}>
      <label
        htmlFor={id}
        style={{
          display: 'block',
          fontSize: 'var(--font-size-sm)',
          fontWeight: 600,
          color: 'var(--ink)',
        }}
      >
        {label}
        {required && (
          <span aria-hidden="true" style={{ color: 'var(--error)', marginLeft: 'var(--space-1)' }}>
            *
          </span>
        )}
      </label>

      {/* El hijo recibe aria-describedby implícito a través del ID */}
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(
            child as React.ReactElement<
              React.HTMLAttributes<HTMLElement> & { 'aria-describedby'?: string; 'aria-invalid'?: boolean | 'true' | 'false' }
            >,
            {
              'aria-describedby':
                [hintId, errorId].filter(Boolean).join(' ') || undefined,
              'aria-invalid': error ? 'true' : undefined,
            },
          );
        }
        return child;
      })}

      {hint && !error && (
        <p
          id={hintId}
          style={{
            margin: 0,
            fontSize: 'var(--font-size-xs)',
            color: 'var(--slate-500)',
          }}
        >
          {hint}
        </p>
      )}

      {error && (
        <p
          id={errorId}
          role="alert"
          style={{
            margin: 0,
            fontSize: 'var(--font-size-xs)',
            color: 'var(--error)',
            fontWeight: 500,
          }}
        >
          {error}
        </p>
      )}
    </div>
  );
}
