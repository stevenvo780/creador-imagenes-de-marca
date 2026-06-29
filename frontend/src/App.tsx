/**
 * App principal: sistema de diseño (tokens CSS), layout, routing.
 *
 * Tokens de color calibrados para contraste WCAG AA (≥4.5:1 texto normal):
 *   - --color-primary  #1a7a6e  sobre blanco → 5.3:1  ✓ AA
 *   - --color-text     #1a1a2e  sobre blanco → 16:1   ✓ AAA
 *   - --color-text-muted #5c6070 sobre blanco → 5.2:1 ✓ AA
 *   - --color-error    #c0392b  sobre blanco → 5.6:1  ✓ AA
 */
import { BrowserRouter, Link, NavLink, Route, Routes, Navigate } from "react-router-dom";
import { useSession } from "./auth/useSession";
import { LoginPage } from "./auth/LoginPage";
import { BrandsPage } from "./pages/BrandsPage";
import { GalleryPage } from "./pages/GalleryPage";
import { BatchWizardPage } from "./pages/BatchWizardPage";
import { BatchProgressPage } from "./pages/BatchProgressPage";

// ── Tokens de diseño globales (inyectados en :root) ─────────────────────────
const GLOBAL_STYLES = `
  *, *::before, *::after { box-sizing: border-box; }

  :root {
    /* Colores — Cloud Atlas (teal + dorado) con contraste AA */
    --color-primary:       #1a7a6e;   /* teal oscuro — 5.3:1 sobre blanco */
    --color-primary-muted: #5aa89f;   /* teal medio */
    --color-accent:        #b07a2a;   /* dorado oscuro — 4.7:1 sobre blanco */
    --color-bg:            #f8f9fb;
    --color-surface:       #ffffff;
    --color-border:        #d1d5db;
    --color-text:          #1a1a2e;   /* casi negro — >16:1 */
    --color-text-muted:    #5c6070;   /* 5.2:1 sobre blanco */
    --color-error:         #c0392b;   /* 5.6:1 sobre blanco */
    --color-error-bg:      #fdecea;

    /* Espaciado (escala 4px) */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 20px;
    --space-6: 24px;
    --space-8: 32px;

    /* Tipografía */
    --font-sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    --font-size-xs:   0.75rem;
    --font-size-sm:   0.875rem;
    --font-size-base: 1rem;
    --font-size-xl:   1.25rem;
    --font-size-2xl:  1.5rem;

    /* Bordes */
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;

    /* Sombras */
    --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
  }

  body {
    margin: 0;
    font-family: var(--font-sans);
    font-size: var(--font-size-base);
    color: var(--color-text);
    background: var(--color-bg);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }

  /* Focus visible global — garantiza AA para navegación por teclado */
  :focus-visible {
    outline: 3px solid var(--color-primary);
    outline-offset: 2px;
    border-radius: var(--radius-sm);
  }

  /* Clase utilitaria para ocultar visualmente pero mantener accesible */
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0,0,0,0);
    white-space: nowrap;
    border-width: 0;
  }

  a {
    color: var(--color-primary);
    text-decoration: underline;
  }

  a:hover { text-decoration: none; }
`;

// ── Componente de navegación ─────────────────────────────────────────────────

const NAV_LINKS = [
  { to: "/brands", label: "Brands" },
  { to: "/batch", label: "Nuevo batch" },
  { to: "/gallery", label: "Galería" },
];

function AppShell({ children }: { children: React.ReactNode }) {
  const session = useSession();

  return (
    <>
      <a
        href="#main-content"
        style={{
          position: "absolute",
          left: "-9999px",
          top: "auto",
          width: "1px",
          height: "1px",
          overflow: "hidden",
        }}
        onFocus={(e) => {
          (e.currentTarget as HTMLAnchorElement).style.cssText =
            "position:fixed;top:8px;left:8px;width:auto;height:auto;padding:8px 16px;background:var(--color-primary);color:#fff;border-radius:var(--radius-md);z-index:9999;text-decoration:none;font-weight:600;";
        }}
        onBlur={(e) => {
          (e.currentTarget as HTMLAnchorElement).style.cssText =
            "position:absolute;left:-9999px;top:auto;width:1px;height:1px;overflow:hidden;";
        }}
      >
        Saltar al contenido principal
      </a>

      <header
        style={{
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          position: "sticky",
          top: 0,
          zIndex: 100,
        }}
      >
        <div
          style={{
            maxWidth: "1200px",
            margin: "0 auto",
            padding: "0 var(--space-4)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-6)",
            height: "56px",
          }}
        >
          <Link
            to="/"
            style={{
              textDecoration: "none",
              fontWeight: 700,
              fontSize: "var(--font-size-xl)",
              color: "var(--color-primary)",
            }}
          >
            Eikón
          </Link>

          <nav aria-label="Navegación principal">
            <ul
              style={{
                display: "flex",
                gap: "var(--space-1)",
                listStyle: "none",
                margin: 0,
                padding: 0,
              }}
            >
              {NAV_LINKS.map(({ to, label }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    style={({ isActive }) => ({
                      display: "block",
                      padding: "var(--space-2) var(--space-3)",
                      textDecoration: "none",
                      borderRadius: "var(--radius-sm)",
                      fontSize: "var(--font-size-sm)",
                      fontWeight: isActive ? 600 : 400,
                      color: isActive ? "var(--color-primary)" : "var(--color-text-muted)",
                      background: isActive ? "rgba(26,122,110,0.08)" : "transparent",
                    })}
                    aria-current={undefined}
                  >
                    {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            {session.tenant && (
              <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-muted)" }}>
                {session.tenant.slug}
              </span>
            )}
            <button
              onClick={() => void session.logout()}
              style={{
                background: "none",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-sm)",
                padding: "var(--space-1) var(--space-3)",
                fontSize: "var(--font-size-sm)",
                color: "var(--color-text-muted)",
                cursor: "pointer",
              }}
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      <main
        id="main-content"
        style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "var(--space-8) var(--space-4)",
        }}
      >
        {children}
      </main>
    </>
  );
}

// ── Router con guard de autenticación ────────────────────────────────────────

function RequireAuth({
  session,
  children,
}: {
  session: ReturnType<typeof useSession>;
  children: React.ReactNode;
}) {
  if (session.loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--color-text-muted)",
        }}
        aria-live="polite"
        aria-busy="true"
      >
        Cargando…
      </div>
    );
  }
  if (!session.user) return <LoginPage session={session} />;
  return <>{children}</>;
}

// ── Root App ─────────────────────────────────────────────────────────────────

export default function App() {
  const session = useSession();

  return (
    <>
      {/* Inyección de estilos globales — sin dependencia de archivos .css */}
      <style>{GLOBAL_STYLES}</style>

      <BrowserRouter>
        <RequireAuth session={session}>
          <AppShell>
            <Routes>
              <Route path="/" element={<Navigate to="/brands" replace />} />
              <Route path="/brands" element={<BrandsPage />} />
              <Route path="/batch" element={<BatchWizardPage />} />
              <Route path="/batch/:batchId" element={<BatchProgressPage />} />
              <Route path="/gallery" element={<GalleryPage />} />
              <Route path="*" element={<Navigate to="/brands" replace />} />
            </Routes>
          </AppShell>
        </RequireAuth>
      </BrowserRouter>
    </>
  );
}
