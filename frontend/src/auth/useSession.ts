/**
 * Hook de sesión: carga /auth/me al montar y expone user/tenant + acciones.
 * Mantiene el estado de autenticación global para el SPA.
 */
import { useCallback, useEffect, useState } from "react";
import { auth, type AuthPayload, ApiError } from "../api/client";

export interface Session {
  loading: boolean;
  user: AuthPayload["user"] | null;
  tenant: AuthPayload["tenant"] | null;
  login: (email: string, password: string) => Promise<void>;
  register: (params: {
    tenant_slug: string;
    tenant_name: string;
    email: string;
    password: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
}

export function useSession(): Session {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<AuthPayload["user"] | null>(null);
  const [tenant, setTenant] = useState<AuthPayload["tenant"] | null>(null);

  const hydrateFromPayload = (payload: AuthPayload) => {
    setUser(payload.user);
    setTenant(payload.tenant);
  };

  // Intenta restaurar la sesión desde la cookie persistida.
  useEffect(() => {
    let cancelled = false;
    auth
      .me()
      .then((payload) => {
        if (!cancelled) hydrateFromPayload(payload);
      })
      .catch((err) => {
        // 401 es esperado cuando no hay sesión activa; cualquier otro error se ignora.
        if (err instanceof ApiError && err.status !== 401) {
          console.error("session restore error", err);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const payload = await auth.login({ email, password });
    hydrateFromPayload(payload);
  }, []);

  const register = useCallback(
    async (params: {
      tenant_slug: string;
      tenant_name: string;
      email: string;
      password: string;
    }) => {
      const payload = await auth.register(params);
      hydrateFromPayload(payload);
    },
    [],
  );

  const logout = useCallback(async () => {
    await auth.logout();
    setUser(null);
    setTenant(null);
  }, []);

  return { loading, user, tenant, login, register, logout };
}
