/**
 * Steps — indicador de progreso para wizards multi-paso.
 * Muestra una línea horizontal con burbujas numeradas y etiquetas.
 */
import React from 'react';

export interface StepItem {
  id: string;
  label: string;
}

export interface StepsProps {
  steps: StepItem[];
  /** Índice 0-based del paso activo */
  currentIndex: number;
}

export function Steps({ steps, currentIndex }: StepsProps) {
  return (
    <nav aria-label="Pasos del proceso">
      {/* Burbujas + líneas */}
      <ol
        role="list"
        style={{
          display: 'flex',
          alignItems: 'center',
          listStyle: 'none',
          margin: 0,
          padding: 0,
        }}
      >
        {steps.map((step, i) => {
          const isDone   = i < currentIndex;
          const isActive = i === currentIndex;

          return (
            <React.Fragment key={step.id}>
              <li
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 'var(--space-1)',
                  position: 'relative',
                  zIndex: 1,
                }}
              >
                {/* Burbuja */}
                <div
                  aria-current={isActive ? 'step' : undefined}
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 'var(--font-size-sm)',
                    fontWeight: 700,
                    fontFamily: 'var(--font-display)',
                    transition: 'background var(--transition-normal), border-color var(--transition-normal)',
                    background: isDone || isActive ? 'var(--teal)' : 'var(--surface-2)',
                    color:  isDone || isActive ? 'var(--teal-ink)' : 'var(--text-muted)',
                    border: isDone || isActive
                      ? '2px solid var(--teal)'
                      : '2px solid var(--border)',
                  }}
                >
                  {isDone ? '✓' : i + 1}
                </div>

                {/* Etiqueta */}
                <span
                  style={{
                    fontSize: 'var(--font-size-xs)',
                    fontWeight: isActive ? 700 : 400,
                    color: isActive ? 'var(--teal)' : 'var(--text-muted)',
                    whiteSpace: 'nowrap',
                    textAlign: 'center',
                  }}
                >
                  {step.label}
                </span>
              </li>

              {/* Conector entre pasos */}
              {i < steps.length - 1 && (
                <li
                  aria-hidden="true"
                  style={{
                    flex: 1,
                    height: '2px',
                    marginBottom: 'calc(var(--font-size-xs) * 1.5 + var(--space-1))',
                    background: i < currentIndex ? 'var(--teal)' : 'var(--border)',
                    transition: 'background var(--transition-normal)',
                  }}
                />
              )}
            </React.Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
