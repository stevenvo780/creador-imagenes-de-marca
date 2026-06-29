/**
 * Button — Cloud Atlas design system
 * Variantes: primary (teal), secondary (borde), ghost (sin fondo)
 * Tamaños: sm, md
 * Estado busy: muestra "procesando" y bloquea interacción
 */
import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md';
  busy?: boolean;
  children: React.ReactNode;
}

const variantStyles: Record<
  NonNullable<ButtonProps['variant']>,
  React.CSSProperties
> = {
  primary: {
    background: 'var(--teal-600)',
    color: '#fff',
    border: '2px solid transparent',
  },
  secondary: {
    background: 'var(--white)',
    color: 'var(--ink)',
    border: '2px solid var(--line)',
  },
  ghost: {
    background: 'transparent',
    color: 'var(--teal-600)',
    border: '2px solid transparent',
  },
};

const sizeStyles: Record<
  NonNullable<ButtonProps['size']>,
  React.CSSProperties
> = {
  sm: {
    padding: 'var(--space-1) var(--space-3)',
    fontSize: 'var(--font-size-sm)',
    borderRadius: 'var(--radius-sm)',
  },
  md: {
    padding: 'var(--space-2) var(--space-5)',
    fontSize: 'var(--font-size-base)',
    borderRadius: 'var(--radius-md)',
  },
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      variant = 'primary',
      size = 'md',
      busy = false,
      children,
      disabled,
      style,
      ...props
    },
    ref,
  ) {
    const isDisabled = disabled || busy;

    const computedStyle: React.CSSProperties = {
      // Base
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 'var(--space-2)',
      fontFamily: 'var(--font-body)',
      fontWeight: 600,
      cursor: isDisabled ? 'not-allowed' : 'pointer',
      transition:
        'background var(--transition-fast), border-color var(--transition-fast), opacity var(--transition-fast)',
      textDecoration: 'none',
      whiteSpace: 'nowrap',
      opacity: isDisabled ? 0.6 : 1,
      // Variant
      ...variantStyles[variant],
      // Size
      ...sizeStyles[size],
      // Consumer overrides
      ...style,
    };

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        aria-busy={busy}
        style={computedStyle}
        {...props}
      >
        {children}
      </button>
    );
  },
);
