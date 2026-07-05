/**
 * Button — Eikon editorial design system
 * Variantes: primary (teal), secondary (borde), ghost (sin fondo), danger
 * Tamaños: sm, md
 * Estado busy: muestra "procesando" y bloquea interacción
 */
import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md';
  busy?: boolean;
  children: React.ReactNode;
}

const variantStyles: Record<
  NonNullable<ButtonProps['variant']>,
  React.CSSProperties
> = {
  primary: {
    background: 'var(--teal)',
    color: 'var(--teal-ink)',
    border: '1.5px solid transparent',
  },
  secondary: {
    background: 'transparent',
    color: 'var(--text)',
    border: '1.5px solid var(--border)',
  },
  ghost: {
    background: 'transparent',
    color: 'var(--teal)',
    border: '1.5px solid transparent',
  },
  danger: {
    background: 'transparent',
    color: 'var(--danger)',
    border: '1.5px solid var(--danger)',
  },
};

const sizeStyles: Record<
  NonNullable<ButtonProps['size']>,
  React.CSSProperties
> = {
  sm: {
    padding: 'var(--space-2) var(--space-3)',
    fontSize: 'var(--font-size-sm)',
    borderRadius: 'var(--r-sm)',
    minHeight: 32,
  },
  md: {
    padding: 'var(--space-3) var(--space-4)',
    fontSize: 'var(--font-size-base)',
    borderRadius: 'var(--r-md)',
    minHeight: 44,
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
      className,
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
        'background var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast), filter var(--transition-fast), opacity var(--transition-fast)',
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
        className={[variant === 'primary' ? 'eikon-primary-hover' : 'eikon-button-hover', className]
          .filter(Boolean)
          .join(' ')}
        style={computedStyle}
        {...props}
      >
        {children}
      </button>
    );
  },
);
