import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider, ThemeSelector } from "./ThemeProvider";
import { AppShell } from "../components/AppShell";

let systemDark = false;
const mediaListeners = new Set<() => void>();
beforeEach(() => {
  localStorage.clear();
  systemDark = false;
  mediaListeners.clear();
  vi.stubGlobal("matchMedia", () => ({
    get matches() { return systemDark; },
    addEventListener: (_: string, listener: () => void) => mediaListeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => mediaListeners.delete(listener),
  }));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); delete document.documentElement.dataset.theme; });

it("cambia toda la interfaz, conserva la preferencia al navegar y al volver a montar", async () => {
  const app = <ThemeProvider><MemoryRouter initialEntries={["/publications"]}>
    <AppShell onLogout={() => {}} tenantSlug="humanizar">
      <Routes>
        <Route path="/publications" element={<h1>Agenda</h1>} />
        <Route path="/brands" element={<h1>Marcas de Humanizar</h1>} />
      </Routes>
    </AppShell>
  </MemoryRouter></ThemeProvider>;
  const view = render(app); const user = userEvent.setup();
  await user.selectOptions(screen.getByRole("combobox", { name: "Tema de la interfaz" }), "dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
  await user.click(screen.getByRole("link", { name: "Marcas" }));
  expect(screen.getByRole("heading", { name: "Marcas de Humanizar" })).toBeTruthy();
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem("eikon.theme")).toBe("dark");
  view.unmount(); render(app);
  expect(document.documentElement.dataset.theme).toBe("dark");
  await user.selectOptions(screen.getByRole("combobox"), "light");
  expect(document.documentElement.dataset.theme).toBe("light");
});

it("sigue los cambios del sistema sólo cuando está seleccionada esa opción", async () => {
  render(<ThemeProvider><ThemeSelector /></ThemeProvider>);
  expect(document.documentElement.dataset.theme).toBe("light");
  act(() => { systemDark = true; mediaListeners.forEach(listener => listener()); });
  expect(document.documentElement.dataset.theme).toBe("dark");
  await userEvent.setup().selectOptions(screen.getByRole("combobox"), "light");
  act(() => { mediaListeners.forEach(listener => listener()); });
  expect(document.documentElement.dataset.theme).toBe("light");
  cleanup(); expect(mediaListeners.size).toBe(0);
});

it("el selector funciona con teclado", async () => {
  render(<ThemeProvider><ThemeSelector /></ThemeProvider>);
  await userEvent.setup().tab();
  expect(document.activeElement).toBe(screen.getByRole("combobox", { name: "Tema de la interfaz" }));
});

it("funciona durante la visita si el navegador bloquea el almacenamiento", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
  render(<ThemeProvider><ThemeSelector /></ThemeProvider>);
  await userEvent.setup().selectOptions(screen.getByRole("combobox"), "dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
});

it("sincroniza el tema de otra pestaña sin confundir sessionStorage", () => {
  render(<ThemeProvider><ThemeSelector /></ThemeProvider>);
  act(() => window.dispatchEvent(new StorageEvent("storage", { key: "eikon.theme", newValue: "dark", storageArea: sessionStorage })));
  expect(document.documentElement.dataset.theme).toBe("light");
  act(() => window.dispatchEvent(new StorageEvent("storage", { key: "eikon.theme", newValue: "dark", storageArea: localStorage })));
  expect(document.documentElement.dataset.theme).toBe("dark");
});
