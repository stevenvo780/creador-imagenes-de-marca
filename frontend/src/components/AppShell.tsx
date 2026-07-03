/**
 * AppShell — envoltorio global de la app: skip link, nav superior fija, main.
 * Navegación en español: Marcas · Crear · Galería
 * Accesible: skip link, aria-label, foco visible, responsive.
 */
import React from 'react';
import { Link, NavLink } from 'react-router-dom';

export interface AppShellProps {
  children: React.ReactNode;
  /** Slug del tenant / cuenta para mostrar en la barra de usuario */
  tenantSlug?: string | null;
  /** Callback al presionar "Salir" */
  onLogout: () => void | Promise<void>;
}

const NAV_LINKS: Array<{ to: string; label: string }> = [
  { to: '/brands', label: 'Marcas' },
  { to: '/studio', label: 'Estudio' },
  { to: '/batch',  label: 'Crear'  },
  { to: '/gallery', label: 'Galería' },
];

export function AppShell({ children, tenantSlug, onLogout }: AppShellProps) {
  return (
    <>
      {/* Skip link — accesibilidad por teclado */}
      <a
        href="#main-content"
        style={{
          position: 'absolute',
          left: '-9999px',
          top: 'auto',
          width: '1px',
          height: '1px',
          overflow: 'hidden',
          zIndex: 9999,
        }}
        onFocus={(e) => {
          Object.assign(e.currentTarget.style, {
            position: 'fixed',
            top: 'var(--space-2)',
            left: 'var(--space-2)',
            width: 'auto',
            height: 'auto',
            padding: 'var(--space-2) var(--space-4)',
            background: 'var(--teal-600)',
            color: '#fff',
            borderRadius: 'var(--radius-md)',
            textDecoration: 'none',
            fontWeight: 600,
            fontSize: 'var(--font-size-sm)',
          });
        }}
        onBlur={(e) => {
          Object.assign(e.currentTarget.style, {
            position: 'absolute',
            left: '-9999px',
            top: 'auto',
            width: '1px',
            height: '1px',
            overflow: 'hidden',
          });
        }}
      >
        Saltar al contenido principal
      </a>

      {/* Header / Barra de navegación */}
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 100,
          background: 'var(--white)',
          borderBottom: '1px solid var(--line)',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        <div
          className="eikon-appbar-inner"
          style={{
            maxWidth: 'var(--content-max)',
            margin: '0 auto',
            padding: '0 var(--space-4)',
            height: 'var(--nav-height)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-6)',
          }}
        >
          {/* Wordmark */}
          <Link
            to="/"
            style={{
              textDecoration: 'none',
              fontFamily: 'var(--font-display)',
              fontWeight: 700,
              fontSize: 'var(--font-size-xl)',
              color: 'var(--teal-600)',
              letterSpacing: '-0.5px',
              flexShrink: 0,
            }}
          >
            Eikón
          </Link>

          {/* Nav principal */}
          <nav aria-label="Navegación principal" className="eikon-appbar-nav" style={{ flex: 1 }}>
            <ul
              style={{
                display: 'flex',
                gap: 'var(--space-1)',
                listStyle: 'none',
                margin: 0,
                padding: 0,
              }}
            >
              {NAV_LINKS.map(({ to, label }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    style={({ isActive }) => ({
                      display: 'block',
                      padding: 'var(--space-2) var(--space-3)',
                      textDecoration: 'none',
                      borderRadius: 'var(--radius-md)',
                      fontSize: 'var(--font-size-sm)',
                      fontWeight: isActive ? 700 : 400,
                      color: isActive ? 'var(--teal-600)' : 'var(--slate-500)',
                      background: isActive ? 'var(--mist)' : 'transparent',
                      transition:
                        'background var(--transition-fast), color var(--transition-fast)',
                    })}
                  >
                    {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          {/* Área de usuario */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-3)',
              flexShrink: 0,
            }}
          >
            {tenantSlug && (
              <span
                className="eikon-appbar-tenant"
                title={`Cuenta: ${tenantSlug}`}
                style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--slate-500)',
                  fontFamily: 'var(--font-mono)',
                  background: 'var(--mist)',
                  padding: '2px var(--space-2)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--line)',
                  maxWidth: 140,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {tenantSlug}
              </span>
            )}

            <button
              type="button"
              onClick={() => void onLogout()}
              style={{
                background: 'none',
                border: '1.5px solid var(--line)',
                borderRadius: 'var(--radius-md)',
                padding: 'var(--space-1) var(--space-3)',
                fontSize: 'var(--font-size-sm)',
                color: 'var(--slate-700)',
                cursor: 'pointer',
                fontFamily: 'var(--font-body)',
                fontWeight: 500,
                transition:
                  'border-color var(--transition-fast), background var(--transition-fast)',
              }}
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      {/* Contenido principal */}
      <main
        id="main-content"
        style={{
          maxWidth: 'var(--content-max)',
          margin: '0 auto',
          padding: 'var(--space-8) var(--space-4)',
          minHeight: 'calc(100vh - var(--nav-height))',
        }}
      >
        {children}
      </main>
    </>
  );
}
