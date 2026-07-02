from __future__ import annotations

from typing import Any

LAYOUT_SELECTORS = (
    "h1,h2,h3,p,span,a,li,"
    "[data-required-text],"
    ".headline,.subhead,.title,.claim,.tagline,.wordmark,.desc,.cta"
)

LAYOUT_WARNING_SEVERITY: dict[str, str] = {
    "empty_required_text": "fail",
    "off_viewport": "fail",
    "overflow_x": "warn",
    "overflow_y": "warn",
    "inspection_error": "warn",
}


def classify_layout_warning(warning: dict[str, Any]) -> str:
    """Pure: clasifica la severidad de UN warning de layout."""
    if not isinstance(warning, dict):
        return "info"
    wtype = str(warning.get("type", ""))
    return LAYOUT_WARNING_SEVERITY.get(wtype, "info")


def aggregate_layout_status(warnings: list[dict[str, Any]]) -> str:
    """Pure: agrega severidades en un status global."""
    if not warnings:
        return "pass"
    severities = {classify_layout_warning(w) for w in warnings}
    if "fail" in severities:
        return "fail"
    if "warn" in severities:
        return "warn"
    return "pass"


LAYOUT_INSPECTION_JS = r"""
() => {
  const SELECTORS = "h1,h2,h3,p,span,a,li,[data-required-text],.headline,.subhead,.title,.claim,.tagline,.wordmark,.desc,.cta";
  const vw = document.documentElement.clientWidth || window.innerWidth || 0;
  const vh = document.documentElement.clientHeight || window.innerHeight || 0;
  const warnings = [];

  function describeEl(el) {
    try {
      const tag = (el.tagName || "").toLowerCase();
      const id = el.id ? "#" + el.id : "";
      const cls = (typeof el.className === "string" ? el.className : "")
        .split(/\s+/).filter(Boolean).slice(0, 3).map(c => "." + c).join("");
      const attr = el.hasAttribute("data-required-text") ? "[data-required-text]" : "";
      const text = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40);
      return (tag + id + cls + attr + (text ? " \"" + text + "\"" : "")).trim();
    } catch (e) {
      return "<unknown>";
    }
  }

  const elements = document.querySelectorAll(SELECTORS);
  elements.forEach((el) => {
    let style, rect;
    try {
      style = window.getComputedStyle(el);
      rect = el.getBoundingClientRect();
    } catch (e) {
      return;
    }
    if (!style) return;

    if (style.display === "none" || style.visibility === "hidden") return;
    if (parseFloat(style.opacity || "1") === 0) return;

    const text = (el.textContent || "").trim();

    if (el.hasAttribute("data-required-text") && text.length === 0) {
      warnings.push({
        type: "empty_required_text",
        selector: describeEl(el),
        detail: "data-required-text element is empty"
      });
    }

    if (el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1) {
      warnings.push({
        type: "overflow_x",
        selector: describeEl(el),
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
        detail: "scrollWidth " + el.scrollWidth + " > clientWidth " + el.clientWidth
      });
    }
    if (el.clientHeight > 0 && el.scrollHeight > el.clientHeight + 1) {
      warnings.push({
        type: "overflow_y",
        selector: describeEl(el),
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
        detail: "scrollHeight " + el.scrollHeight + " > clientHeight " + el.clientHeight
      });
    }

    if (rect.width > 0 && rect.height > 0 && vw > 0 && vh > 0) {
      if (rect.right < 0 || rect.bottom < 0 || rect.left > vw || rect.top > vh) {
        warnings.push({
          type: "off_viewport",
          selector: describeEl(el),
          rect: {
            left: Math.round(rect.left), top: Math.round(rect.top),
            right: Math.round(rect.right), bottom: Math.round(rect.bottom)
          },
          viewport: { width: vw, height: vh },
          detail: "element rect outside viewport"
        });
      }
    }
  });

  return { viewport: { width: vw, height: vh }, warnings: warnings };
}
"""
