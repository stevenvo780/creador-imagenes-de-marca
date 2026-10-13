/* Aplicar la preferencia antes de cargar la SPA evita un cambio de color inicial. */
(function () {
  var preference = "system";
  try {
    var saved = localStorage.getItem("eikon.theme");
    if (saved === "light" || saved === "dark") preference = saved;
  } catch (_) { /* La interfaz funciona también sin almacenamiento local. */ }
  var dark = typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = preference === "system" ? (dark ? "dark" : "light") : preference;
})();
