/**
 * App — routing principal + guard de autenticación.
 * Los tokens de diseño viven en styles/theme.css (Cloud Atlas).
 * El AppShell con la nav en español está en components/AppShell.tsx.
 */
import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import "./styles/theme.css";

import { useSession } from "./auth/useSession";
import { LoginPage } from "./auth/LoginPage";
import { BrandsPage } from "./pages/BrandsPage";
import { BrandEditorPage } from "./pages/Brands/BrandEditorPage";
import BrandIdentityPage from "./pages/BrandIdentityPage";
import { AssetStudioPage } from "./pages/AssetStudioPage";
import { MediaGallery } from "./pages/Media";
import { PublicationsPage } from "./pages/Publications/PublicationsPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { clearPrivateMedia } from "./api/media";
import { createContext, useContext, useState } from "react";
import "./pages/Media/media.css";
import { BatchWizardPage } from "./pages/BatchWizardPage";
import { BatchProgressPage } from "./pages/BatchProgressPage";

import { AppShell } from "./components/AppShell";
import { Spinner } from "./components/Spinner";

const OwnerContext = createContext(false);
const TenantContext = createContext("");
function PublicationsRoute() {
  return (
    <PublicationsPage
      owner={useContext(OwnerContext)}
      tenant={useContext(TenantContext)}
    />
  );
}
function GalleryRoute() {
  return <MediaGallery owner={useContext(OwnerContext)} />;
}

// ── Guard de autenticación ─────────────────────────────────────────────────────

function RequireAuth({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const [exiting, setExiting] = useState(false);

  if (session.loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "var(--space-3)",
          color: "var(--slate-500)",
          fontFamily: "var(--font-body)",
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
      owner={session.user.role === "owner"}
      onLogout={async () => {
        clearPrivateMedia();
        setExiting(true);
        try {
          await session.logout();
        } finally {
          setExiting(false);
        }
      }}
    >
      {!exiting && (
        <OwnerContext.Provider value={session.user.role === "owner"}>
          <TenantContext.Provider value={session.tenant?.slug || ""}>
            <div key={`${session.tenant?.slug}:${session.user.email}`}>
              {children}
            </div>
          </TenantContext.Provider>
        </OwnerContext.Provider>
      )}
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
          <Route path="/" element={<Navigate to="/brands" replace />} />
          <Route path="/brands" element={<BrandsPage />} />
          <Route path="/brands/:brandId/edit" element={<BrandEditorPage />} />
          <Route
            path="/brands/:brandId/identity"
            element={<BrandIdentityPage />}
          />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/studio" element={<AssetStudioPage />} />
          <Route path="/batch" element={<BatchWizardPage />} />
          <Route path="/batch/:batchId" element={<BatchProgressPage />} />
          <Route path="/publications" element={<PublicationsRoute />} />
          <Route
            path="/publications/campaigns/:campaignId"
            element={<PublicationsRoute />}
          />
          <Route path="/gallery" element={<GalleryRoute />} />
          <Route path="*" element={<Navigate to="/brands" replace />} />
        </Routes>
      </RequireAuth>
    </BrowserRouter>
  );
}
