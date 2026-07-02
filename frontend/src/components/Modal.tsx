/**
 * Modal / Lightbox — diálogo con trampa de foco (WCAG AA).
 * Cierra con Escape. Bloquea scroll del body mientras está abierto.
 * No requiere un portal; usa position:fixed para salir del flujo normal.
 */
import React, { useEffect, useRef } from 'react';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  /** Ancho máximo del panel. Default: 520px */
  maxWidth?: string;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

export function Modal({
  open,
  onClose,
  title,
  children,
  maxWidth = '520px',
}: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Bloquear scroll del body
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Focus trap + Escape
  useEffect(() => {
    if (!open || !dialogRef.current) return;
    const dialog = dialogRef.current;

    // Mover el foco al diálogo al abrir
    const firstFocusable = dialog.querySelector<HTMLElement>(FOCUSABLE);
    firstFocusable?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;

      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last  = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Overlay */}
      <div
        aria-hidden="true"
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(14, 27, 26, 0.5)',
          zIndex: 200,
          backdropFilter: 'blur(2px)',
        }}
      />

      {/* Panel */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 201,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 'var(--space-4)',
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            background: 'var(--white)',
            borderRadius: 'var(--radius-xl)',
            boxShadow: 'var(--shadow-lg)',
            width: '100%',
            maxWidth,
            maxHeight: 'calc(100vh - var(--space-8))',
            overflowY: 'auto',
            pointerEvents: 'all',
            animation: 'eikon-fadein 180ms ease',
          }}
        >
          {/* Cabecera */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: 'var(--space-5) var(--space-6)',
              borderBottom: '1px solid var(--line)',
            }}
          >
            <h2
              id="modal-title"
              style={{
                margin: 0,
                fontFamily: 'var(--font-display)',
                fontSize: 'var(--font-size-xl)',
                color: 'var(--ink)',
              }}
            >
              {title}
            </h2>
            <button
              type="button"
              onClick={onClose}
              aria-label="Cerrar"
              style={{
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--slate-500)',
                fontSize: 'var(--font-size-xl)',
                lineHeight: 1,
                // Tap target mínimo 44×44 (WCAG 2.5.5) — el contenido (✕)
                // queda centrado dentro del área interactiva.
                minWidth: 44,
                minHeight: 44,
                padding: 'var(--space-2)',
                borderRadius: 'var(--radius-sm)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition:
                  'color var(--transition-fast), background var(--transition-fast)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--ink)';
                e.currentTarget.style.background = 'var(--mist)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--slate-500)';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              ✕
            </button>
          </div>

          {/* Contenido */}
          <div style={{ padding: 'var(--space-6)' }}>{children}</div>
        </div>
      </div>
    </>
  );
}
