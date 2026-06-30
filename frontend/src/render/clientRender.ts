/**
 * Client-side render module para Eikón.
 * Renderiza combinaciones de marca a PNG en el navegador del usuario
 * usando modern-screenshot y la FontFace API.
 */

import { clientRender, RenderSpec, RenderCombination } from "../api/client";

interface FontLoadConfig {
  family: string;
  weight: number | string;
  style?: string;
  url: string;
}

/**
 * Carga fuentes desde /static/fonts/ usando la FontFace API.
 * Retorna un array de FontFace objects para monitorear carga.
 */
function loadFontsFromSpec(): FontFace[] {
  // Mapa de fuentes: (family, weight) -> archivo woff2
  // Basado en templates/eikon-system.css
  const fontConfigs: FontLoadConfig[] = [
    { family: "Inter", weight: 400, url: "/static/fonts/Inter-400.woff2" },
    { family: "Inter", weight: 700, url: "/static/fonts/Inter-700.woff2" },
    {
      family: "Playfair Display",
      weight: 400,
      url: "/static/fonts/PlayfairDisplay-400.woff2",
    },
    {
      family: "Playfair Display",
      weight: 700,
      url: "/static/fonts/PlayfairDisplay-700.woff2",
    },
    {
      family: "Playfair Display",
      weight: 900,
      url: "/static/fonts/PlayfairDisplay-900.woff2",
    },
    {
      family: "Space Grotesk",
      weight: 500,
      url: "/static/fonts/SpaceGrotesk-500.woff2",
    },
    {
      family: "Space Grotesk",
      weight: 700,
      url: "/static/fonts/SpaceGrotesk-700.woff2",
    },
  ];

  const loadedFonts: FontFace[] = [];

  for (const config of fontConfigs) {
    try {
      const fontFace = new FontFace(
        config.family,
        `url('${config.url}')`,
        {
          weight: String(config.weight),
          style: config.style || "normal",
        }
      );

      document.fonts.add(fontFace);
      loadedFonts.push(fontFace);
    } catch (e) {
      console.warn(
        `Failed to add font ${config.family} ${config.weight}: ${e}`
      );
    }
  }

  return loadedFonts;
}

/**
 * Precarua fuentes con timeout de 3 segundos.
 * Si falla, continúa sin abortar.
 */
async function preloadFonts(): Promise<{ success: number; failed: number }> {
  loadFontsFromSpec();

  try {
    const fontPromise = document.fonts.ready;
    const timeoutPromise = new Promise<void>((_, reject) =>
      setTimeout(() => reject(new Error("Font loading timeout")), 3000)
    );

    await Promise.race([fontPromise, timeoutPromise]);
    return { success: document.fonts.size, failed: 0 };
  } catch (e) {
    console.warn("Font preload timeout or error:", e);
    return { success: 0, failed: document.fonts.size };
  }
}

/**
 * Fetchea el HTML de la plantilla desde /api/v1/templates/{name}
 */
async function fetchTemplateHtml(templateName: string): Promise<string> {
  const res = await fetch(`/api/v1/templates/${templateName}`, {
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch template: ${res.status}`);
  }
  return res.text();
}

/**
 * Monta la plantilla en un div oculto, aplica vars/data-attrs/isotipo/textos,
 * y retorna el nodo del contenedor.
 */
function createAndMountContainer(
  templateHtml: string,
  combination: RenderCombination,
  viewport: { w: number; h: number }
): HTMLDivElement {
  // Crear contenedor oculto
  const container = document.createElement("div");
  container.style.position = "fixed";
  container.style.left = "-99999px";
  container.style.top = "-99999px";
  container.style.width = `${viewport.w}px`;
  container.style.height = `${viewport.h}px`;
  container.style.overflow = "hidden";

  // Parsear el HTML
  const parser = new DOMParser();
  const doc = parser.parseFromString(templateHtml, "text/html");

  // Copiar el body al contenedor
  const bodyContent = doc.body;
  container.appendChild(bodyContent);

  // Aplicar vars como CSS custom properties
  const styleElement = document.createElement("style");
  let styleContent = `:root {`;

  for (const [key, value] of Object.entries(combination.vars)) {
    // Convertir keys a CSS custom props: primario -> --primario
    const cssKey = `--${key}`;
    styleContent += `\n  ${cssKey}: ${value};`;
  }

  styleContent += "\n}";
  styleElement.textContent = styleContent;
  container.insertBefore(styleElement, container.firstChild);

  // Setear data-attrs en el root del contenedor (body)
  for (const [attr, value] of Object.entries(combination.data_attrs)) {
    container.setAttribute(attr, value);
  }

  // Inyectar isotipo como <img> en [data-isotype-container]
  const isotopeContainer = container.querySelector(
    "[data-isotype-container]"
  );
  if (isotopeContainer && combination.isotype_data_uri) {
    const img = document.createElement("img");
    img.src = combination.isotype_data_uri;
    img.style.width = "100%";
    img.style.height = "100%";
    img.style.display = "block";
    // Limpiar y reemplazar contenido
    isotopeContainer.textContent = "";
    isotopeContainer.appendChild(img);
  }

  // Rellenar textos vía data-* attributes
  for (const [key, value] of Object.entries(combination.texts)) {
    // Buscar elementos con data-{key}
    const selector = `[data-${key}]`;
    const elements = container.querySelectorAll(selector);
    elements.forEach((el) => {
      el.textContent = value;
    });
  }

  document.body.appendChild(container);
  return container;
}

/**
 * Rasteriza un nodo DOM a PNG usando modern-screenshot.
 * Retorna un Blob o dataURL.
 *
 * Nota: modern-screenshot se instala en npm install y debe estar en package.json.
 * El import dinámico evita errores en tiempo de desarrollo antes de instalar.
 */
async function rasterizeToPng(
  node: HTMLElement,
  width: number,
  height: number,
  pixelRatio: number
): Promise<Blob> {
  const { domToPng } = await import("modern-screenshot");

  // En modern-screenshot la escala de salida (device_scale_factor) es `scale`.
  const dataUrl = await domToPng(node, {
    width,
    height,
    scale: pixelRatio,
  });

  // Convertir dataURL a Blob
  const blobStr = dataUrl.split(",")[1];
  if (!blobStr) throw new Error("Invalid rasterization output");
  const binaryString = atob(blobStr);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }

  return new Blob([bytes], { type: "image/png" });
}

/**
 * Renderiza una combinación: monta, rastreriza, sube.
 */
async function renderAndUploadCombination(
  batchId: number,
  templateHtml: string,
  combination: RenderCombination,
  viewport: { w: number; h: number },
  deviceScaleFactor: number,
  assetType: string
): Promise<{ success: boolean; error?: string }> {
  let container: HTMLDivElement | null = null;

  try {
    // Montar container
    container = createAndMountContainer(templateHtml, combination, viewport);

    // Esperar a que las fuentes estén listas
    await document.fonts.ready;

    // Doble requestAnimationFrame para asegurar que el render haya completado
    await new Promise((resolve) => requestAnimationFrame(resolve));
    await new Promise((resolve) => requestAnimationFrame(resolve));

    // Rasterizar
    const pngBlob = await rasterizeToPng(
      container,
      viewport.w,
      viewport.h,
      deviceScaleFactor
    );

    // Preparar FormData para upload
    const formData = new FormData();
    formData.append("combo_idx", String(combination.idx));
    formData.append("asset_type", assetType);
    formData.append("params", JSON.stringify(combination.params));
    const paddedIdx = String(combination.idx).padStart(3, "0");
    formData.append("image", pngBlob, `combo_${paddedIdx}.png`);

    // Subir con reintentos (robustez ante fallos transitorios de red).
    let lastErr: unknown = null;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        await clientRender.upload(batchId, formData);
        lastErr = null;
        break;
      } catch (e) {
        lastErr = e;
        await new Promise((r) => setTimeout(r, 400 * (attempt + 1)));
      }
    }
    if (lastErr) throw lastErr;

    return { success: true };
  } catch (e) {
    return {
      success: false,
      error: e instanceof Error ? e.message : String(e),
    };
  } finally {
    // Limpiar
    if (container && container.parentNode) {
      container.parentNode.removeChild(container);
    }
  }
}

/**
 * Función principal: renderiza todas las combinaciones en el navegador.
 *
 * Parámetros:
 * - batchId: ID del batch
 * - onProgress: callback opcional para progreso (llamado después de cada combo)
 *
 * Retorna:
 * - { uploaded: number; failed: number }
 */
export async function renderBatchClientSide(
  batchId: number,
  onProgress?: (done: number, total: number) => void
): Promise<{ uploaded: number; failed: number }> {
  let uploaded = 0;
  let failed = 0;

  try {
    // 1. Fetch render-spec
    const spec: RenderSpec = await clientRender.plan(batchId);

    // 2. Precargar fuentes
    await preloadFonts();

    // 3. Fetch plantilla HTML una sola vez
    const templateHtml = await fetchTemplateHtml(spec.template_name);

    // 4. Procesar combinaciones
    const total = spec.combinations.length;
    for (let i = 0; i < total; i++) {
      const combo = spec.combinations[i];

      const result = await renderAndUploadCombination(
        batchId,
        templateHtml,
        combo,
        spec.viewport,
        spec.device_scale_factor,
        spec.asset_type
      );

      if (result.success) {
        uploaded++;
      } else {
        failed++;
        console.warn(
          `Combo ${combo.idx} failed:`,
          result.error
        );
      }

      // Reportar progreso
      if (onProgress) {
        onProgress(uploaded + failed, total);
      }
    }
  } catch (e) {
    console.error("renderBatchClientSide error:", e);
    // Si falla el plan/plantilla, no podemos saber el total
    // Reportar error pero no crashear
  }

  return { uploaded, failed };
}
