import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ThemeProvider } from "./theme/ThemeProvider";

const container = document.getElementById("root");
if (!container) throw new Error("No se encontró #root en el DOM.");

createRoot(container).render(
  <StrictMode>
    <ThemeProvider><App /></ThemeProvider>
  </StrictMode>,
);
