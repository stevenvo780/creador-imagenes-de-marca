/**
 * Input — campo de texto base, accesible (AA).
 * Usalo dentro de <Field> para label + hint + error automáticos,
 * o de forma standalone con aria-label.
 */
import React from 'react';

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  hasError?: boolean;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  function Input({ hasError = false, style, ...props }, ref) {
    const computedStyle: React.CSSProperties = {
      display: 'block',
      width: '100%',
      padding: 'var(--space-2) var(--space-3)',
      fontFamily: 'var(--font-body)',
      fontSize: 'var(--font-size-base)',
      color: 'var(--ink)',
      background: 'var(--paper)',
      border: hasError
        ? '1.5px solid var(--error)'
        : '1.5px solid var(--line)',
      borderRadius: 'var(--radius-md)',
      outline: 'none',
      transition:
        'border-color var(--transition-fast), box-shadow var(--transition-fast)',
      boxSizing: 'border-box',
      ...style,
    };

    return <input ref={ref} style={computedStyle} {...props} />;
  },
);
