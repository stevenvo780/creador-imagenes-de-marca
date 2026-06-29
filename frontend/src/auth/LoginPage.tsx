/**
 * Página de login / registro — accesible (AA contrast, focus states, aria-live).
 */
import { type FormEvent, useState } from "react";
import { ApiError } from "../api/client";
import type { Session } from "./useSession";

interface Props {
  session: Session;
}

export function LoginPage({ session }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Campos de login
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Campos extra de registro
  const [tenantSlug, setTenantSlug] = useState("");
  const [tenantName, setTenantName] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") {
        await session.login(email, password);
      } else {
        await session.register({
          tenant_slug: tenantSlug,
          tenant_name: tenantName,
          email,
          password,
        });
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Error inesperado. Intenta de nuevo.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--color-bg)",
        padding: "var(--space-4)",
      }}
    >
      <div
        style={{
          background: "var(--color-surface)",
          borderRadius: "var(--radius-lg)",
          padding: "var(--space-8)",
          width: "100%",
          maxWidth: "400px",
          boxShadow: "var(--shadow-md)",
        }}
      >
        {/* Marca */}
        <div style={{ textAlign: "center", marginBottom: "var(--space-6)" }}>
          <h1
            style={{
              fontSize: "var(--font-size-2xl)",
              fontWeight: 700,
              color: "var(--color-primary)",
              margin: 0,
            }}
          >
            Eikón
          </h1>
          <p
            style={{
              color: "var(--color-text-muted)",
              fontSize: "var(--font-size-sm)",
              marginTop: "var(--space-1)",
            }}
          >
            Generador de assets de marca
          </p>
        </div>

        {/* Tabs accesibles */}
        <div
          role="tablist"
          aria-label="Modo de acceso"
          style={{
            display: "flex",
            borderBottom: "2px solid var(--color-border)",
            marginBottom: "var(--space-6)",
          }}
        >
          <button
            role="tab"
            aria-selected={mode === "login"}
            onClick={() => setMode("login")}
            style={{
              flex: 1,
              padding: "var(--space-2) var(--space-3)",
              background: "none",
              border: "none",
              borderBottom:
                mode === "login"
                  ? "2px solid var(--color-primary)"
                  : "2px solid transparent",
              color:
                mode === "login"
                  ? "var(--color-primary)"
                  : "var(--color-text-muted)",
              fontWeight: mode === "login" ? 600 : 400,
              cursor: "pointer",
              fontSize: "var(--font-size-sm)",
              marginBottom: "-2px",
            }}
          >
            Iniciar sesión
          </button>
          <button
            role="tab"
            aria-selected={mode === "register"}
            onClick={() => setMode("register")}
            style={{
              flex: 1,
              padding: "var(--space-2) var(--space-3)",
              background: "none",
              border: "none",
              borderBottom:
                mode === "register"
                  ? "2px solid var(--color-primary)"
                  : "2px solid transparent",
              color:
                mode === "register"
                  ? "var(--color-primary)"
                  : "var(--color-text-muted)",
              fontWeight: mode === "register" ? 600 : 400,
              cursor: "pointer",
              fontSize: "var(--font-size-sm)",
              marginBottom: "-2px",
            }}
          >
            Registrar tenant
          </button>
        </div>

        {/* Formulario */}
        <form onSubmit={handleSubmit} noValidate>
          {mode === "register" && (
            <>
              <div style={{ marginBottom: "var(--space-4)" }}>
                <label htmlFor="tenant-slug" style={labelStyle}>
                  Slug del tenant
                </label>
                <input
                  id="tenant-slug"
                  type="text"
                  required
                  minLength={2}
                  maxLength={80}
                  value={tenantSlug}
                  onChange={(e) => setTenantSlug(e.target.value)}
                  placeholder="mi-empresa"
                  style={inputStyle}
                  aria-describedby="tenant-slug-hint"
                />
                <p id="tenant-slug-hint" style={hintStyle}>
                  Identificador único, solo letras, números y guiones.
                </p>
              </div>
              <div style={{ marginBottom: "var(--space-4)" }}>
                <label htmlFor="tenant-name" style={labelStyle}>
                  Nombre del tenant
                </label>
                <input
                  id="tenant-name"
                  type="text"
                  required
                  minLength={2}
                  maxLength={120}
                  value={tenantName}
                  onChange={(e) => setTenantName(e.target.value)}
                  placeholder="Mi Empresa S.A."
                  style={inputStyle}
                />
              </div>
            </>
          )}

          <div style={{ marginBottom: "var(--space-4)" }}>
            <label htmlFor="email" style={labelStyle}>
              Correo electrónico
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="usuario@ejemplo.com"
              style={inputStyle}
            />
          </div>

          <div style={{ marginBottom: "var(--space-6)" }}>
            <label htmlFor="password" style={labelStyle}>
              Contraseña
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              autoComplete={
                mode === "register" ? "new-password" : "current-password"
              }
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mínimo 8 caracteres"
              style={inputStyle}
            />
          </div>

          {/* Mensaje de error accesible */}
          <div aria-live="assertive" aria-atomic="true">
            {error && (
              <p
                style={{
                  color: "var(--color-error)",
                  fontSize: "var(--font-size-sm)",
                  marginBottom: "var(--space-4)",
                  padding: "var(--space-2) var(--space-3)",
                  background: "var(--color-error-bg)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--color-error)",
                }}
                role="alert"
              >
                {error}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={busy}
            style={{
              width: "100%",
              padding: "var(--space-3) var(--space-4)",
              background: busy
                ? "var(--color-primary-muted)"
                : "var(--color-primary)",
              color: "#fff",
              border: "none",
              borderRadius: "var(--radius-md)",
              fontSize: "var(--font-size-base)",
              fontWeight: 600,
              cursor: busy ? "not-allowed" : "pointer",
              transition: "background 0.15s",
            }}
            aria-busy={busy}
          >
            {busy
              ? "Procesando…"
              : mode === "login"
                ? "Entrar"
                : "Crear cuenta"}
          </button>
        </form>
      </div>
    </main>
  );
}

// ── Estilos inline reutilizables ────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: "var(--space-1)",
  fontSize: "var(--font-size-sm)",
  fontWeight: 500,
  color: "var(--color-text)",
};

const inputStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "var(--space-2) var(--space-3)",
  border: "1.5px solid var(--color-border)",
  borderRadius: "var(--radius-sm)",
  fontSize: "var(--font-size-base)",
  color: "var(--color-text)",
  background: "var(--color-bg)",
  boxSizing: "border-box",
  outline: "none",
  transition: "border-color 0.15s, box-shadow 0.15s",
};

const hintStyle: React.CSSProperties = {
  margin: "var(--space-1) 0 0",
  fontSize: "var(--font-size-xs)",
  color: "var(--color-text-muted)",
};
