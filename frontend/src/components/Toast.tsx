/**
 * Toast / Banner — notificación inline controlada por el padre.
 * Variantes: info, success, error
 * Para notificaciones flotantes se necesita un portal; este componente
 * es inline (se inserta donde el padre lo coloque en el DOM).
 */

export interface ToastProps {
  message: string;
  variant?: 'info' | 'success' | 'error';
  onClose?: () => void;
}

const variantMap: Record<
  NonNullable<ToastProps['variant']>,
  { bg: string; color: string; border: string; icon: string }
> = {
  info: {
    bg: 'var(--mist)',
    color: 'var(--slate-700)',
    border: 'var(--line)',
    icon: 'ℹ',
  },
  success: {
    bg: '#e6f9f0',
    color: '#1a7a4a',
    border: '#a7e0c4',
    icon: '✓',
  },
  error: {
    bg: 'var(--error-bg)',
    color: 'var(--error)',
    border: '#f5b4b0',
    icon: '✕',
  },
};

export function Toast({
  message,
  variant = 'info',
  onClose,
}: ToastProps) {
  const v = variantMap[variant];

  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      aria-live={variant === 'error' ? 'assertive' : 'polite'}
      aria-atomic="true"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        padding: 'var(--space-3) var(--space-4)',
        background: v.bg,
        color: v.color,
        border: `1px solid ${v.border}`,
        borderRadius: 'var(--radius-md)',
        fontSize: 'var(--font-size-sm)',
        fontWeight: 500,
        animation: 'eikon-fadein 180ms ease',
      }}
    >
      <span aria-hidden="true" style={{ flexShrink: 0, fontWeight: 700 }}>
        {v.icon}
      </span>

      <span style={{ flex: 1 }}>{message}</span>

      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Cerrar notificación"
          style={{
            flexShrink: 0,
            background: 'none',
            border: 'none',
            color: 'inherit',
            cursor: 'pointer',
            padding: '0 var(--space-1)',
            fontSize: 'var(--font-size-base)',
            lineHeight: 1,
            opacity: 0.7,
          }}
        >
          ✕
        </button>
      )}
    </div>
  );
}
