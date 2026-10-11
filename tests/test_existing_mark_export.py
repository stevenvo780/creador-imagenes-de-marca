"""Exportar geometría existente sin elegir signos arbitrarios ni redibujar."""

import hashlib
import xml.etree.ElementTree as ET

import pytest

from scripts.export_existing_marks import (
    export_aletheia_glyph,
    export_aletheia_symbol,
    export_cauce,
)


def test_cauce_preserves_fragment_and_geometry():
    fragment = '<svg class="mark" viewBox="0 0 32 32" fill="none"><defs><linearGradient id="bm"><stop offset="0" stop-color="#5fe0ea"/></linearGradient></defs><path d="M3 11c5 0 5 5 10 5" stroke="url(#bm)" stroke-width="2.6"/></svg>'
    source = f'<header>{fragment}<svg id="themeIco"></svg></header>'
    result = export_cauce(source)
    assert result["source_fragment_sha256"] == hashlib.sha256(fragment.encode()).hexdigest()
    assert result["svg"] == fragment.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    tree = ET.fromstring(result["svg"])
    assert tree.find("{http://www.w3.org/2000/svg}path").attrib["d"] == "M3 11c5 0 5 5 10 5"
    assert result["role"] == "existing_product_symbol"


@pytest.mark.parametrize(
    "source", ['<svg id="themeIco"></svg>', '<svg class="mark"></svg><svg class="mark"></svg>']
)
def test_cauce_requires_one_explicit_mark(source):
    with pytest.raises(ValueError):
        export_cauce(source)


def test_aletheia_keeps_glyph_and_resolves_declared_light_token():
    fragment = '<svg viewBox="0 0 16 16" width="12" height="12" fill="none"><path d="M1 12 L1 4 M5.5 12 L5.5 1" stroke="var(--measure)" strokeWidth="1.6" strokeLinecap="round" /></svg>'
    source = "function Wordmark(): ReactNode { return (" + fragment + "); }\nfunction NavList() {}"
    result = export_aletheia_glyph(
        source,
        ":root { --measure: #4338ca; } @media (prefers-color-scheme:dark) { :root { --measure:#8b90e8; } }",
    )
    tree = ET.fromstring(result["svg"])
    path = tree.find("{http://www.w3.org/2000/svg}path")
    assert path.attrib == {
        "d": "M1 12 L1 4 M5.5 12 L5.5 1",
        "stroke": "#4338ca",
        "stroke-width": "1.6",
        "stroke-linecap": "round",
    }
    assert result["source_fragment_sha256"] == hashlib.sha256(fragment.encode()).hexdigest()
    assert result["role"] == "existing_ui_glyph_only"
    assert result["full_wordmark"] is False
    assert result["resolved_tokens"] == {"--measure": "#4338ca"}


def test_aletheia_rejects_unresolved_token():
    source = (
        'function Wordmark(): ReactNode { return (<svg><path stroke="var(--measure)" /></svg>); }'
    )
    with pytest.raises(ValueError):
        export_aletheia_glyph(source, ":root { --other:#4338ca; }")


ALETHEIA = """function Wordmark(): ReactNode { return (
<span className="flex items-center gap-2.5">
<span aria-hidden="true" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--radius-sm)] border"
style={{ borderColor: 'var(--rule)', backgroundColor: 'var(--measure-soft)' }}>
<svg viewBox="0 0 16 16" width="12" height="12" fill="none" role="presentation">
<path d="M1 12 L1 4 M5.5 12 L5.5 1 M10 12 L10 6 M14.5 12 L14.5 3" stroke="var(--measure)" strokeWidth="1.6" strokeLinecap="round" />
</svg></span><span>Aletheia</span></span>); }
function NavList() {}"""
ALETHEIA_CSS = ":root { --rule:#dfe3ea; --measure:#4338ca; --measure-soft:#eef0fe; } :root { --radius-sm:0.25rem; }"


def test_aletheia_recovers_complete_existing_symbol():
    result = export_aletheia_symbol(ALETHEIA, ALETHEIA_CSS)
    tree = ET.fromstring(result["svg"])
    ns = "{http://www.w3.org/2000/svg}"
    assert tree.attrib["viewBox"] == "0 0 28 28"
    assert tree.find(ns + "rect").attrib == {
        "x": "0.5",
        "y": "0.5",
        "width": "27",
        "height": "27",
        "rx": "3.5",
        "fill": "#eef0fe",
        "stroke": "#dfe3ea",
        "stroke-width": "1",
    }
    glyph = tree.find(ns + "svg")
    assert glyph.attrib["x"] == glyph.attrib["y"] == "8"
    assert glyph.attrib["width"] == glyph.attrib["height"] == "12"
    assert glyph.find(ns + "path").attrib["d"] in ALETHEIA
    assert result["role"] == "existing_product_symbol"
    assert result["full_wordmark"] is False


@pytest.mark.parametrize(
    "old,new",
    [
        ("h-7", "h-8"),
        ("borderColor", "outlineColor"),
        ('width="12"', 'width="14"'),
        ("justify-center", "justify-start"),
        ("borderColor:", "borderWidth:4, borderColor:"),
        ("borderColor:", "transform:'scale(2)', borderColor:"),
    ],
)
def test_aletheia_symbol_rejects_changed_container(old, new):
    with pytest.raises(ValueError):
        export_aletheia_symbol(ALETHEIA.replace(old, new), ALETHEIA_CSS)


@pytest.mark.parametrize(
    "css",
    [
        ALETHEIA_CSS.replace("--radius-sm:0.25rem;", ""),
        ALETHEIA_CSS.replace("--rule:#dfe3ea;", ""),
        ALETHEIA_CSS + "html { font-size:18px; }",
        ALETHEIA_CSS + ":root { --spacing:0.5rem; }",
    ],
)
def test_aletheia_symbol_rejects_unproven_geometry(css):
    with pytest.raises(ValueError):
        export_aletheia_symbol(ALETHEIA, css)
