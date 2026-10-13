import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type ThemePreference = "light" | "dark" | "system";
const STORAGE_KEY = "eikon.theme";
const ThemeContext = createContext<{
  preference: ThemePreference;
  setPreference: (value: ThemePreference) => void;
} | null>(null);

function validPreference(value: string | null): ThemePreference {
  return value === "light" || value === "dark" ? value : "system";
}

function readPreference(): ThemePreference {
  try { return validPreference(localStorage.getItem(STORAGE_KEY)); }
  catch { return "system"; }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreference] = useState<ThemePreference>(readPreference);
  useEffect(() => {
    const media = typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    const apply = () => {
      document.documentElement.dataset.theme = preference === "system"
        ? (media?.matches ? "dark" : "light") : preference;
    };
    apply();
    media?.addEventListener("change", apply);
    return () => media?.removeEventListener("change", apply);
  }, [preference]);

  useEffect(() => {
    const sync = (event: StorageEvent) => {
      try {
        if (event.storageArea === localStorage && (event.key === STORAGE_KEY || event.key === null)) {
          setPreference(validPreference(event.newValue));
        }
      } catch { /* No depender del almacenamiento para operar la interfaz. */ }
    };
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  const choose = (value: ThemePreference) => {
    setPreference(value);
    try { localStorage.setItem(STORAGE_KEY, value); }
    catch { /* Conservar el tema durante esta visita si el navegador no permite guardar. */ }
  };
  return <ThemeContext.Provider value={{ preference, setPreference: choose }}>{children}</ThemeContext.Provider>;
}

export function ThemeSelector() {
  const theme = useContext(ThemeContext);
  if (!theme) throw new Error("El selector de tema requiere ThemeProvider.");
  return <label className="eikon-theme-selector">
    <span>Tema</span>
    <select aria-label="Tema de la interfaz" value={theme.preference}
      onChange={event => theme.setPreference(event.target.value as ThemePreference)}>
      <option value="light">Claro</option>
      <option value="dark">Oscuro</option>
      <option value="system">Sistema</option>
    </select>
  </label>;
}
