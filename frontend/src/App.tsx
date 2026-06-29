/**
 * App — routing principal + guard de autenticación.
 * Los tokens de diseño viven en styles/theme.css (Cloud Atlas).
 * El AppShell con la nav en español está en components/AppShell.tsx.
 */
import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom';
import './styles/theme.css';

import { useSession }        from './auth/useSession';
import { LoginPage }         from './auth/LoginPage';
import { BrandsPage }        from './pages/BrandsPage';
import { GalleryPage }       from './pages/GalleryPage';
import { BatchWizardPage }   from './pages/BatchWizardPage';
import { BatchProgressPage } from './pages/BatchProgressPage';

import { AppShell } from './components/AppShell';
import { Spinner }  from './components/Spinner';

// ── Guard de autenticación ─────────────────────────────────────────────────────

function RequireAuth({ children }: { children: React.ReactNode }) {
  const session = useSession();

  if (session.loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 'var(--space-3)',
          color: 'var(--slate-500)',
          fontFamily: 'var(--font-body)',
        }}
        aria-live="polite"
        aria-busy="true"
      >
        <Spinner size="md" label="Verificando sesión…" />
        <span>Cargando…</span>
      </div>
    );
  }

  if (!session.user) {
    return <LoginPage session={session} />;
  }

  return (
    <AppShell
      tenantSlug={session.tenant?.slug}
      onLogout={() => void session.logout()}
    >
      {children}
    </AppShell>
  );
}

// ── Root App ──────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <BrowserRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <RequireAuth>
        <Routes>
          <Route path="/"                 element={<Navigate to="/brands" replace />} />
          <Route path="/brands"           element={<BrandsPage />} />
          <Route path="/batch"            element={<BatchWizardPage />} />
          <Route path="/batch/:batchId"   element={<BatchProgressPage />} />
          <Route path="/gallery"          element={<GalleryPage />} />
          <Route path="*"                 element={<Navigate to="/brands" replace />} />
        </Routes>
      </RequireAuth>
    </BrowserRouter>
  );
}
