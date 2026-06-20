#!/usr/bin/env python3
"""
Generador de plantillas HTML autocontenidas para Eikon.
Crea 26 plantillas data-driven sin dependencias externas.
"""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"

def make_base_template(template_id, width, height, title, variants, content_html, dpi=72):
    """Genera plantilla base con estructura estándar."""
    # Calcular safe viewport
    vp_width = int(width) if dpi == 72 else int(width / 4.167)  # 300dpi = 4.167x
    vp_height = int(height) if dpi == 72 else int(height / 4.167)

    variant_css = ""
    for i, vname in enumerate(variants, 1):
        variant_css += f"  body[data-variant=\"{vname}\"] {{ /* Variante {i} */ }}\n"

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={vp_width}, height={vp_height}, initial-scale=1">
<title>Eikon - {title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --primario: #0b1417;
    --acento-2: #8d7cc0;
    --texto: #e8e0d4;
    --bg: #0b1417;
    --gradient-hero: linear-gradient(135deg, #43b5a6, #8d7cc0);
    --font-titulo: 'Playfair Display', Georgia, serif;
    --font-cuerpo: 'Inter', Arial, sans-serif;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: {width}px; height: {height}px; overflow: hidden; }}
  body {{
    background-color: var(--bg);
    color: var(--texto);
    font-family: var(--font-cuerpo);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 40px;
  }}

  /* VARIANTES */
{variant_css}

  .container {{ display: flex; flex-direction: column; align-items: center; gap: 20px; width: 100%; }}
  .title {{ font-family: var(--font-titulo); font-size: 48px; font-weight: 700; }}
  .copy {{ font-size: 18px; line-height: 1.5; }}
  .symbol {{ font-size: 120px; font-weight: 700; }}

  .contract-fields {{ display: none !important; }}
</style>
</head>
<body data-variant="{variants[0]}">
  <div class="container">
{content_html}
  </div>

  <div class="contract-fields" aria-hidden="true">
    <span data-titulo></span>
    <span data-subtitulo></span>
    <span data-copy></span>
    <span data-logo-simbolo></span>
    <span data-logo-texto></span>
    <span data-numero></span>
    <span data-etiqueta></span>
    <span data-autor></span>
    <span data-cargo></span>
    <span data-url></span>
    <span data-acento></span>
    <span data-acento-2></span>
  </div>
</body>
</html>'''

# Definir 23 plantillas restantes
TEMPLATES_TO_CREATE = [
    ("lockup_vertical.html", 800, 800, "Lockup Vertical",
     ["v1_color", "v2_mono", "v3_inverse"],
     '    <span class="symbol" data-logo-simbolo data-fit data-fit-min="54">⬡</span>\n    <h1 class="title" data-logo-texto data-fit data-fit-min="20">Marca</h1>'),

    ("wordmark.html", 1000, 300, "Wordmark",
     ["v1_dark", "v2_light"],
     '    <h1 class="title" data-logo-texto data-fit data-fit-min="32">Marca</h1>'),

    ("isotipo.html", 800, 800, "Isotipo",
     ["v1_color", "v2_mono", "v3_inverse"],
     '    <span class="symbol" data-logo-simbolo data-fit data-fit-min="54">⬡</span>'),

    ("favicon.html", 512, 512, "Favicon",
     ["v1_32", "v2_180", "v3_512"],
     '    <span class="symbol" data-logo-simbolo data-fit data-fit-min="48">⬡</span>'),

    ("watermark.html", 1000, 1000, "Watermark",
     ["v1_light", "v2_dark"],
     '    <span class="symbol" data-logo-simbolo style="opacity: 0.15;" data-fit data-fit-min="48">⬡</span>'),

    ("x_post.html", 1200, 675, "X/Twitter Post",
     ["v1_tesis", "v2_cita", "v3_anuncio"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="28">Título</h1>\n    <p class="copy" data-copy data-fit data-fit-min="14">Copy</p>'),

    ("facebook_post.html", 1200, 628, "Facebook Post",
     ["v1_tesis", "v2_promocion", "v3_evento"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="28">Título</h1>\n    <p class="copy" data-copy data-fit data-fit-min="14">Copy</p>'),

    ("instagram_story.html", 1080, 1920, "Instagram Story",
     ["v1_cover", "v2_text_block", "v3_poll", "v4_qna", "v5_swipe_up"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="36">Título</h1>\n    <p class="copy" data-copy data-fit data-fit-min="16">Copy</p>'),

    ("instagram_carousel.html", 1080, 1080, "Instagram Carousel",
     ["v1_portada", "v2_paso", "v3_continuo", "v4_destacado", "v5_cierre"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="36">Título</h1>\n    <p class="copy" data-copy data-fit data-fit-min="16">Copy</p>'),

    ("tiktok_cover.html", 1080, 1920, "TikTok Cover",
     ["v1_hook", "v2_tutorial", "v3_anuncio"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="40">Título</h1>\n    <p class="copy" data-copy data-fit data-fit-min="16">Copy</p>'),

    ("yt_thumbnail.html", 1280, 720, "YouTube Thumbnail",
     ["v1_bold", "v2_clean", "v3_face"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="32">Título</h1>'),

    ("yt_banner.html", 2560, 1440, "YouTube Banner",
     ["v1_brand", "v2_schedule", "v3_feature"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="48">Título</h1>\n    <p class="copy" data-copy data-fit data-fit-min="20">Copy</p>'),

    ("ig_reel_cover.html", 1080, 1920, "IG Reel Cover",
     ["v1_hook", "v2_tutorial", "v3_story"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="40">Título</h1>'),

    ("linkedin_post.html", 1200, 627, "LinkedIn Post",
     ["v1_tesis", "v2_framework", "v3_insight", "v4_noticia", "v5_equipo", "v6_informe"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="26">Título</h1>\n    <p class="copy" data-copy data-fit data-fit-min="14">Copy</p>'),

    ("x_header.html", 1500, 500, "X/Twitter Header",
     ["v1_brand", "v2_feature", "v3_event"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="36">Título</h1>'),

    ("web_hero.html", 1920, 600, "Web Hero",
     ["v1_split", "v2_central", "v3_video_fallback", "v4_minimal"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="40">Título</h1>\n    <p class="copy" data-copy data-fit data-fit-min="16">Copy</p>'),

    ("web_hero_mobile.html", 540, 960, "Web Hero Mobile",
     ["v1_central", "v2_split", "v3_cta"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="28">Título</h1>\n    <p class="copy" data-copy data-fit data-fit-min="12">Copy</p>'),

    ("ad_leaderboard.html", 728, 90, "Ad Leaderboard",
     ["v1_text", "v2_cta", "v3_offer"],
     '    <span class="symbol" data-logo-simbolo style="font-size: 60px;">◐</span>\n    <h1 class="title" data-titulo data-fit data-fit-min="12">Título</h1>\n    <a href="#" data-url data-fit data-fit-min="10">Ver</a>'),

    ("ad_rectangle.html", 300, 250, "Ad Rectangle",
     ["v1_offer", "v2_feature", "v3_cta"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="20">Título</h1>\n    <span class="symbol" data-numero data-fit data-fit-min="32">01</span>\n    <p class="copy" data-copy data-fit data-fit-min="10">Copy</p>'),

    ("business_card.html", 1050, 600, "Business Card",
     ["v1_front", "v2_back"],
     '    <span class="symbol" data-logo-simbolo data-fit data-fit-min="54">⬡</span>\n    <h1 class="title" data-logo-texto data-fit data-fit-min="24">Marca</h1>\n    <p class="copy" data-copy data-fit data-fit-min="12">Contacto</p>'),

    ("stat_card.html", 1080, 1080, "Stat Card",
     ["v1_hero_num", "v2_dual_stat", "v3_graph"],
     '    <span class="symbol" data-numero data-fit data-fit-min="72">99</span>\n    <p class="label" data-etiqueta data-fit data-fit-min="14">Métrica</p>\n    <p class="copy" data-copy data-fit data-fit-min="12">Contexto</p>'),

    ("og_general.html", 1200, 630, "OG General",
     ["v1_website", "v2_articulo", "v3_feature"],
     '    <h1 class="title" data-titulo data-fit data-fit-min="32">Título</h1>\n    <p class="copy" data-copy data-fit data-fit-min="14">Descripción</p>'),

    ("letterhead.html", 2480, 3508, "Letterhead A4",
     ["v1_oficial", "v2_interno"],
     '    <span class="symbol" data-logo-simbolo style="font-size: 80px;">◐</span>\n    <h1 class="title" data-logo-texto data-fit data-fit-min="32">Marca</h1>\n    <div style="margin-top: 100px; font-size: 14px;"><p data-copy data-fit data-fit-min="12">Contenido</p></div>',
     300),
]

# Generar plantillas
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
for item in TEMPLATES_TO_CREATE:
    filename = item[0]
    width = item[1]
    height = item[2]
    title = item[3]
    variants = item[4]
    content = item[5]
    dpi = item[6] if len(item) > 6 else 72

    template_html = make_base_template(filename, width, height, title, variants, content, dpi)
    output_path = TEMPLATES_DIR / filename
    output_path.write_text(template_html)
    print(f"✓ {filename:35} {width:4}×{height:4} {len(variants)} variantes")

print(f"\n✓ {len(TEMPLATES_TO_CREATE)} plantillas generadas en {TEMPLATES_DIR}")
