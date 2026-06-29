from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import traceback

from . import constants as cfg
from .orchestrator import run_generator


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Motor EIKON: Generador Canónico de Assets de Marca",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python eikon.py --marca pinakotheke-kosmos
  python eikon.py --marca pinakotheke-kosmos --dry-run
  python eikon.py --marca pinakotheke-kosmos --resume
  python eikon.py --all
  python eikon.py --marca prizma-iris --solo logos
  python eikon.py --marca pinakotheke-kosmos --skip-contraste
  python eikon.py --marca pinakotheke-kosmos --web-icons
  python web_icons.py --marca pinakotheke-kosmos
  python web_icons.py --all
        """,
    )
    parser.add_argument("--marca", type=str, help="Slug de la marca (ej. pinakotheke-kosmos)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Procesa el set CORE de marcas (ver CORE_MARCAS en eikon_core.constants)",
    )
    parser.add_argument(
        "--all-marcas",
        action="store_true",
        help="Procesa TODAS las marcas registradas (incluye demos no core)",
    )
    parser.add_argument(
        "--only-marcas", type=str, help="Lista separada por comas de slugs a procesar"
    )
    parser.add_argument("--solo", type=str, help="Filtra categoría (ej. logos, cards)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Enumera assets sin renderizar ni escribir PNGs"
    )
    parser.add_argument(
        "--resume",
        "--solo-cambios",
        action="store_true",
        dest="resume",
        help="Usa cache para saltar assets no modificados",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Número de workers paralelos (actualmente limitado a 1)",
    )
    parser.add_argument(
        "--skip-contraste", action="store_true", help="Omite validación WCAG al final"
    )
    parser.add_argument(
        "--clean", action="store_true", help="Limpia output/<marca>/ antes de renderizar (opt-in)"
    )
    parser.add_argument(
        "--fail-on-layout",
        action="store_true",
        help="Exit 1 si algún asset tiene layout_status=fail",
    )
    parser.add_argument(
        "--web-icons", action="store_true", help="Genera favicon/PWA/OG tras render Playwright"
    )
    args = parser.parse_args()

    if not args.marca and not args.all and not args.only_marcas:
        parser.print_help()
        print("\n✗ Error: Especifica --marca <slug>, --all, o --only-marcas <slugs>")
        return 1

    if args.parallel > 1:
        print("⚠ --parallel > 1 no soportado aún. Limitando a 1 worker.", file=sys.stderr)

    marcas_a_procesar: list[str] = []
    if args.all or args.all_marcas:
        if not cfg.MARCAS_DIR.exists():
            print("✗ Directorio marcas/ no existe", file=sys.stderr)
            return 1
        # --all = CORE_MARCAS; --all-marcas = todo
        cores = set(cfg.CORE_MARCAS) if hasattr(cfg, "CORE_MARCAS") else set()
        for f in cfg.MARCAS_DIR.glob("*.json"):
            slug = f.stem
            if args.all_marcas or slug in cores:
                marcas_a_procesar.append(slug)
    elif args.only_marcas:
        marcas_a_procesar = [s.strip() for s in args.only_marcas.split(",") if s.strip()]
    else:
        marcas_a_procesar.append(args.marca)

    if args.clean:
        for slug in marcas_a_procesar:
            brand_output = cfg.OUTPUT_DIR / slug
            if brand_output.exists():
                shutil.rmtree(brand_output)
                print(f"  🗑 Limpiado: {brand_output}")

    try:
        result = asyncio.run(
            run_generator(
                marcas_a_procesar=marcas_a_procesar,
                filtro_categoria=args.solo,
                dry_run=args.dry_run,
                use_cache=args.resume,
                max_parallel=args.parallel,
                skip_contrast=args.skip_contraste,
            )
        )

        print("\n" + "=" * 60 + "\nREPORTE FINAL\n" + "=" * 60)
        totals = result["total"]
        for slug, cats in result["counts"].items():
            total_assets = sum(cats.values())
            print(f"✓ {slug}: {total_assets} assets totales.")
        print(f"  Generados: {totals['generated']}")
        print(f"  Cache hit: {totals['cached']}")
        print(f"  Errores:   {totals['errors']}")
        print(f"  Layout fails: {totals.get('layout_fails', 0)}")
        if result["manifests"]:
            print(f"  Manifests: {len(result['manifests'])}")

        if args.fail_on_layout and totals.get("layout_fails", 0) > 0:
            print(f"  ✗ --fail-on-layout: {totals['layout_fails']} assets con layout_status=fail")
            return 1

        if args.web_icons and not args.dry_run:
            print("\n→ Generando web-icons estándar (favicon, PWA, OG)…")
            try:
                from web_icons import (
                    generate_web_icons,
                    load_brand,
                    print_verification,
                    verify_web_icons,
                )

                for slug in marcas_a_procesar:
                    brand = load_brand(slug)
                    if brand is None:
                        continue
                    wi_results = generate_web_icons(slug, brand, dry_run=False)
                    ok_count = sum(1 for ok, _ in wi_results.values() if ok)
                    print(f"  ✓ {slug}: {ok_count}/{len(wi_results)} web-icons")
                    v = verify_web_icons(slug)
                    print_verification(slug, v)
            except Exception as e_wi:
                print(f"  ⚠ Error en web-icons: {e_wi}", file=sys.stderr)
                traceback.print_exc()

        return 0 if totals["errors"] == 0 else 1

    except Exception as e:
        print(f"✗ Error fatal: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
