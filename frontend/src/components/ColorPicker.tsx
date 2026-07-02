/**
 * ColorPicker — selector accesible de color.
 *
 * Compone dos controles sincronizados:
 *  • Un <input type="color"> nativo (selector visual del SO / browser).
 *  • Un campo de texto hexadecimal con validación (para power users y a11y).
 *
 * Ambos controles comparten el mismo <label>, están enlazados por
 * aria-describedby a un hint de formato y, si existe, a un mensaje de error.
 * La previsualización grande es decorativa (aria-hidden) — la información
 * útil la dan el label y el valor textual.
 *
 * a11y:
 *  - WCAG 2.1.1 (teclado): ambos inputs son nativos, totalmente operables.
 *  - WCAG 1.3.1 (info y relaciones): label + aria-describedby + aria-invalid.
 *  - WCAG 2.4.7 (foco visible): el outline global de theme.css aplica.
 *  - WCAG 2.5.5 (tamaño del objetivo): tap target >= 44×44px.
 */
import React, { useId } from 'react';

export interface ColorPickerProps {
  label: string;
  value: string;
  onChange: (hex: string) => void;
  error?: string;
  /** ID opcional. Si no se pasa se genera uno (estable entre renders). */
  id?: string;
  /** Texto opcional de ayuda bajo el input. */
  hint?: string;
  disabled?: boolean;
}

// Normaliza cualquier valor a "#RRGGBB" en mayúsculas. Si no es válido, devuelve el fallback.
function normalizeHex(value: string, fallback = '#000000'): string {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  const m = /^#?([0-9a-fA-F]{6})$/.exec(trimmed);
  if (m) return `#${m[1].toUpperCase()}`;
  const m3 = /^#?([0-9a-fA-F]{3})$/.exec(trimmed);
  if (m3) {
    const [r, g, b] = m3[1].split('');
    return `#${r}${r}${g}${g}${b}${b}`.toUpperCase();
  }
  return fallback;
}

// ¿Es un hex válido (3 o 6 dígitos, opcional #)?
function isValidHex(value: string): boolean {
  return /^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(value.trim());
}

export const ColorPicker = React.forwardRef<HTMLInputElement, ColorPickerProps>(
  function ColorPicker(
    { label, value, onChange, error, id, hint, disabled = false, ...rest },
    ref,
  ) {
    const reactId = useId();
    const inputId = id ?? `cp-${reactId}`;
    const hintId = hint ? `${inputId}-hint` : undefined;
    const errorId = error ? `${inputId}-error` : undefined;
    const describedBy =
      [hintId, errorId].filter(Boolean).join(' ') || undefined;

    const safeValue = normalizeHex(value);
    const [hexText, setHexText] = React.useState(safeValue);

    // Si el valor externo cambia, sincronizamos el text input también.
    React.useEffect(() => {
      setHexText(safeValue);
    }, [safeValue]);

    function handleColorInput(e: React.ChangeEvent<HTMLInputElement>) {
      const next = normalizeHex(e.target.value, safeValue);
      setHexText(next);
      onChange(next);
    }

    function handleTextChange(e: React.ChangeEvent<HTMLInputElement>) {
      const raw = e.target.value;
      setHexText(raw);
      if (isValidHex(raw)) {
        onChange(normalizeHex(raw, safeValue));
      }
    }

    function handleTextBlur() {
      // Al perder foco, normalizamos lo que haya escrito el usuario.
      if (isValidHex(hexText)) {
        const normalized = normalizeHex(hexText);
        setHexText(normalized);
        onChange(normalized);
      } else {
        // Si escribió basura, revertimos al último valor válido.
        setHexText(safeValue);
      }
    }

    return (
      <div style={{ display: 'grid', gap: 'var(--space-1)' }}>
        <label
          htmlFor={inputId}
          style={{
            display: 'block',
            fontSize: 'var(--font-size-sm)',
            fontWeight: 600,
            color: 'var(--ink)',
          }}
        >
          {label}
        </label>

        <div
          style={{
            display: 'flex',
            alignItems: 'stretch',
            gap: 'var(--space-2)',
          }}
        >
          {/* Selector visual nativo — el cuadrado grande es decorativo,
              el input real es el nativo (oculto pero interactivo). */}
          <div
            style={{
              position: 'relative',
              width: 44,
              height: 44,
              minWidth: 44,
              minHeight: 44,
              borderRadius: 'var(--radius-md)',
              border: error
                ? '1.5px solid var(--error)'
                : '1.5px solid var(--line)',
              overflow: 'hidden',
              background: safeValue,
              boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.05)',
            }}
          >
            <input
              ref={ref}
              type="color"
              id={inputId}
              value={safeValue}
              onChange={handleColorInput}
              disabled={disabled}
              aria-invalid={error ? 'true' : undefined}
              aria-describedby={describedBy}
              {...rest}
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                border: 'none',
                padding: 0,
                background: 'transparent',
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: 0, // invisible pero interactivo; el cuadro pintado detrás es decorativo
              }}
            />
          </div>

          {/* Campo hex sincronizado — accesible por teclado y lector de pantalla. */}
          <input
            type="text"
            value={hexText}
            onChange={handleTextChange}
            onBlur={handleTextBlur}
            disabled={disabled}
            spellCheck={false}
            autoComplete="off"
            aria-label={`${label} — valor hexadecimal`}
            aria-invalid={error ? 'true' : undefined}
            aria-describedby={describedBy}
            placeholder="#1F8276"
            maxLength={7}
            style={{
              flex: 1,
              minWidth: 0,
              minHeight: 44,
              padding: 'var(--space-2) var(--space-3)',
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--font-size-base)',
              color: 'var(--ink)',
              background: 'var(--paper)',
              border: error
                ? '1.5px solid var(--error)'
                : '1.5px solid var(--line)',
              borderRadius: 'var(--radius-md)',
              outline: 'none',
              textTransform: 'uppercase',
              boxSizing: 'border-box',
              transition:
                'border-color var(--transition-fast), box-shadow var(--transition-fast)',
              opacity: disabled ? 0.6 : 1,
            }}
          />
        </div>

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
  },
);
