(function () {
  const root = document.documentElement;
  const body = document.body;
  const params = new URLSearchParams(window.location.search);

  const cssParamMap = {
    bg: "--bg",
    primario: "--primario",
    acento: "--acento",
    "acento-2": "--acento-2",
    acento_2: "--acento-2",
    "acento-3": "--acento-3",
    acento_3: "--acento-3",
    texto: "--texto",
    "texto-muted": "--texto-muted",
    texto_muted: "--texto-muted",
    surface: "--surface",
    "gradient-hero": "--gradient-hero",
    gradient_hero: "--gradient-hero",
    "grad-hero": "--grad-hero",
    grad_hero: "--grad-hero",
    "font-titulo": "--font-titulo",
    font_titulo: "--font-titulo",
    "font-cuerpo": "--font-cuerpo",
    font_cuerpo: "--font-cuerpo"
  };

  const dataParamMap = {
    titulo: "data-titulo",
    subtitulo: "data-subtitulo",
    copy: "data-copy",
    "logo-simbolo": "data-logo-simbolo",
    logo_simbolo: "data-logo-simbolo",
    "logo-texto": "data-logo-texto",
    logo_texto: "data-logo-texto",
    numero: "data-numero",
    etiqueta: "data-etiqueta",
    autor: "data-autor",
    cargo: "data-cargo",
    url: "data-url",
    acento: "data-acento",
    "acento-2": "data-acento-2",
    acento_2: "data-acento-2"
  };

  const stripQuotes = (value) => String(value || "").trim().replace(/^['"]|['"]$/g, "");

  const hexToRgb = (hex) => {
    let value = stripQuotes(hex).replace("#", "");
    if (value.length === 3) value = value.split("").map((ch) => ch + ch).join("");
    if (!/^[0-9a-fA-F]{6}$/.test(value)) return null;
    return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16));
  };

  const firstHex = (value) => {
    const match = String(value || "").match(/#[0-9a-fA-F]{3,6}\b/);
    return match ? match[0] : value;
  };

  const luminance = (rgb) => (0.299 * rgb[0]) + (0.587 * rgb[1]) + (0.114 * rgb[2]);

  const detectLine = () => {
    const slug = (body.dataset.slug || params.get("slug") || "").toLowerCase();
    if (body.dataset.brandLine) return body.dataset.brandLine;
    return slug.startsWith("prizma") ? "prizma" : "cloud";
  };

  const setDataText = (attr, value) => {
    const normalized = String(value || "").replace(/\n/g, " ");
    document.querySelectorAll(`[${attr}]`).forEach((el) => {
      el.textContent = normalized;
      el.dataset.empty = String(!normalized.trim());
    });
  };

  const applyParams = () => {
    const variant = params.get("variant");
    if (variant) body.dataset.variant = variant;

    const slug = params.get("slug");
    if (slug) body.dataset.slug = slug;

    const brandLine = params.get("brand-line") || params.get("brand_line");
    if (brandLine) body.dataset.brandLine = brandLine;

    params.forEach((value, key) => {
      if (cssParamMap[key]) root.style.setProperty(cssParamMap[key], value);
      if (key.startsWith("--")) root.style.setProperty(key, value);
      if (dataParamMap[key]) setDataText(dataParamMap[key], value);
      if (key.startsWith("data-")) setDataText(key, value);
    });
  };

  const computeContrast = () => {
    const styles = getComputedStyle(root);
    const line = detectLine();
    const dark = line === "prizma" ? "#0c0e10" : "#0b1417";
    const light = line === "prizma" ? "#f0ece6" : "#e8e0d4";
    const rawBg = firstHex(styles.getPropertyValue("--bg"));
    const rgb = hexToRgb(rawBg) || hexToRgb(dark);
    const text = luminance(rgb) > 128 ? dark : light;
    root.style.setProperty("--contrast-dark", dark);
    root.style.setProperty("--contrast-light", light);
    root.style.setProperty("--texto-auto", text);
    root.style.setProperty("--contrast-text", text);
    if (!styles.getPropertyValue("--grad-hero").trim()) {
      root.style.setProperty("--grad-hero", styles.getPropertyValue("--gradient-hero"));
    }
  };

  const fitOne = (el) => {
    const min = Number(el.dataset.fitMin || 12);
    let size = Number.parseFloat(getComputedStyle(el).fontSize);
    if (!Number.isFinite(size)) return;
    const overflows = () => {
      const st = getComputedStyle(el);
      const overX = el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2;
      const constrainedY = st.maxHeight !== "none" || el.dataset.fitY === "true";
      const overY = constrainedY && el.clientHeight > 0 && el.scrollHeight > el.clientHeight + 8;
      return overX || overY;
    };
    for (let i = 0; i < 120 && size > min && overflows(); i += 1) {
      size -= 1;
      el.style.fontSize = `${size}px`;
    }
  };

  const fitAll = () => document.querySelectorAll("[data-fit]").forEach(fitOne);

  window.__eikonRuntimeRefresh = () => {
    computeContrast();
    fitAll();
  };
  window.__fitBrandText = fitAll;

  applyParams();
  window.__eikonRuntimeRefresh();
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(window.__eikonRuntimeRefresh).catch(() => {});
  }
})();
