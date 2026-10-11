"""Exportar geometría existente sin elegir signos arbitrarios ni redibujar."""

import hashlib
import xml.etree.ElementTree as ET

import pytest

from scripts.export_existing_marks import export_aletheia_glyph, export_cauce


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
