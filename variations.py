"""
variations.py — Eikon Phase 6 (scaffolding, stdlib-only)

Deterministic variation planner. Pure data + pure functions.
NO TOCA eikon.py. Aporta la base sobre la que Fase 6 conectará el motor
de render con un plan de variaciones generado algorítmicamente.

API pública
-----------
- ``VariationRequest``:  input estructurado (frozen, mutable-dict-friendly).
- ``Variation``:         output individual (frozen, hashable).
- ``VariationPlan``:     plan completo (frozen, hashable).
- ``ExpansionStrategy``: ``Literal["seeded", "round_robin", "cartesian"]``.
- ``deterministic_seed(marca, category, type, variant, idx, salt) -> int``.
- ``expand_variations(count, category, type, base_variants, ...) -> VariationPlan``.
- ``plan_from_request(request) -> VariationPlan``.
- ``validate_request(request) -> None`` (lanza ``ValueError`` si hay errores).
- ``STANDARD_CATEGORIES``: ``frozenset`` con las 5 categorías canónicas.

Diseño
------
- Stdlib-only (``hashlib`` + ``dataclasses`` + ``typing``). Sin Playwright,
  sin numpy, sin PIL. Importable desde cualquier venv.
- Determinismo: SHA-256 de los inputs → ``uint64`` estable entre procesos
  y plataformas. Mismos args → mismo plan. Sin ``time``, sin ``random``.
- Estrategias de combinatoria:
    * ``"seeded"``     — ranking por hash + cycle (default, mejor diversidad).
    * ``"round_robin"`` — ciclo predecible sobre el producto cartesiano.
    * ``"cartesian"``  — primeras N del cartesiano con wrap determinista.
- Inmutabilidad defensiva: ``Variation`` y ``VariationPlan`` son frozen.
  ``VariationRequest`` también frozen; sus ``dict`` internos se asumen
  no mutados por el caller (semántica estándar de dataclass-frozen).

Fase 6 unirá ``VariationPlan`` con ``eikon.py``: por cada ``Variation`` del
plan se invocará el render correspondiente con ``seed`` para reproducir
(cache estable, re-render idempotente, re-batch determinista).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

__version__ = "variations-v0.1-scaffolding"


# Categorías canónicas del motor Eikon. STABLE — usar para validación.
STANDARD_CATEGORIES: frozenset[str] = frozenset(
    {
        "logos",
        "cards",
        "og",
        "stationery",
        "banners",
    }
)

# Tamaño máximo de plan por defecto (safety cap para Fase 6).
DEFAULT_MAX_COUNT: int = 200

# Locale por defecto (passthrough; NO entra al seed).
DEFAULT_LOCALE: str = "es"

ExpansionStrategy = Literal["seeded", "round_robin", "cartesian"]


# =============================================================================
# SEED DETERMINISTA (función pura, stdlib-only)
# =============================================================================


def _stable_int(*parts: str, digest_bytes: int = 8) -> int:
    """SHA-256 → uint64. Estable entre procesos y plataformas.

    Args:
        parts:        Componentes a hashear (se concatenan con ``\\x1f``).
        digest_bytes: Bytes del digest a interpretar (default 8 → uint64).

    Returns:
        int en ``[0, 2**(8*digest_bytes))``.
    """
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")  # unit separator (FS)
    return int.from_bytes(h.digest()[:digest_bytes], "big", signed=False)


def deterministic_seed(
    *,
    marca: str,
    category: str,
    type: str,
    variant: str = "",
    idx: int = 0,
    salt: str = "",
) -> int:
    """Entero ``uint64`` estable a partir de los inputs (función pura).

    Mismos inputs → mismo output. Sin I/O, sin ``time``, sin ``random``.
    Útil para: claves de caché, semilla de RNG, reproducibilidad de re-render.

    Args:
        marca:    slug de la marca (p.ej. ``"pinakotheke-kosmos"``).
        category: una de ``STANDARD_CATEGORIES``.
        type:     tipo de asset (p.ej. ``"lockup_horizontal"``).
        variant:  representación canónica de los params (``"|"``-joined).
        idx:      índice 0-based dentro del plan.
        salt:     sal opcional para diversificar el espacio de seeds.

    Returns:
        ``int`` en ``[0, 2**64)``.
    """
    return _stable_int(
        str(marca),
        str(category),
        str(type),
        str(variant),
        str(int(idx)),
        str(salt),
    )


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass(frozen=True)
class VariationRequest:
    """Input inmutable para ``expand_variations``. Soporta serialización JSON.

    ``frozen=True`` previene reasignaciones; los ``dict`` internos se asumen
    no mutados por el caller. ``__hash__`` se desactiva explícitamente abajo
    (los ``dict`` no son hashables).
    """

    marca: str
    category: str
    type: str
    count: int
    base_variants: dict[str, tuple[str, ...]] = field(default_factory=dict)
    strategy: ExpansionStrategy = "seeded"
    seed_salt: str = ""
    locale: str = DEFAULT_LOCALE
    palette_override: dict[str, str] | None = None
    max_count: int = DEFAULT_MAX_COUNT
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Serializa a ``dict`` JSON-friendly (ejes como listas, no tuplas)."""
        return {
            "marca": self.marca,
            "category": self.category,
            "type": self.type,
            "count": self.count,
            "base_variants": {k: list(v) for k, v in self.base_variants.items()},
            "strategy": self.strategy,
            "seed_salt": self.seed_salt,
            "locale": self.locale,
            "palette_override": (dict(self.palette_override) if self.palette_override else None),
            "max_count": self.max_count,
            "notes": self.notes,
        }


# VariationRequest no es hashable (contiene dicts). Desactivar explícitamente
# para que el mensaje de error sea claro, no un crash genérico de dataclass.
VariationRequest.__hash__ = None  # type: ignore[assignment]


@dataclass(frozen=True)
class Variation:
    """Una variación individual dentro del plan. Inmutable + hashable.

    ``params`` se almacena como ``tuple[tuple[str, str], ...]`` (ordenado) para
    garantizar hashabilidad. ``params_dict()`` expone la vista mutable-friendly.
    """

    idx: int
    seed: int
    params: tuple[tuple[str, str], ...]
    category: str
    type: str
    marca: str
    variant_str: str

    def params_dict(self) -> dict[str, str]:
        """Vista ``dict`` de ``params`` (orden de inserción: alfabético)."""
        return dict(self.params)

    def as_dict(self) -> dict[str, Any]:
        """Serializa a ``dict`` JSON-friendly."""
        return {
            "idx": self.idx,
            "seed": self.seed,
            "params": self.params_dict(),
            "category": self.category,
            "type": self.type,
            "marca": self.marca,
            "variant": self.variant_str,
        }


@dataclass(frozen=True)
class VariationPlan:
    """Plan completo de ``N`` variaciones. Inmutable; igualdad por contenido."""

    request: VariationRequest
    variations: tuple[Variation, ...]
    strategy_used: ExpansionStrategy

    def __len__(self) -> int:
        return len(self.variations)

    def __iter__(self):
        return iter(self.variations)

    def __getitem__(self, idx: int) -> Variation:
        # Soporta índices negativos (delegamos a tuple).
        return self.variations[idx]

    def to_dict(self) -> dict[str, Any]:
        """Serializa el plan a ``dict`` JSON-friendly."""
        return {
            "request": {
                "marca": self.request.marca,
                "category": self.request.category,
                "type": self.request.type,
                "count": self.request.count,
                "strategy": self.strategy_used,
                "seed_salt": self.request.seed_salt,
                "locale": self.request.locale,
            },
            "variations": [v.as_dict() for v in self.variations],
        }

    def to_jsonl(self) -> str:
        """Serializa a JSONL (una variación por línea). Vacío → string vacío."""
        if not self.variations:
            return ""
        return (
            "\n".join(
                json.dumps(v.as_dict(), ensure_ascii=False, sort_keys=True) for v in self.variations
            )
            + "\n"
        )


# VariationPlan no es hashable (contiene VariationRequest con dicts).
VariationPlan.__hash__ = None  # type: ignore[assignment]


# =============================================================================
# VALIDACIÓN
# =============================================================================


def validate_request(req: VariationRequest) -> None:
    """Valida un ``VariationRequest``. Lanza ``ValueError`` si hay problemas.

    El mensaje de error incluye el campo concreto y el valor recibido para
    que el caller (CLI, UI) pueda mostrar feedback accionable.
    """
    if not isinstance(req.marca, str) or not req.marca.strip():
        raise ValueError(f"VariationRequest.marca debe ser str no-vacío, got {req.marca!r}")
    if not isinstance(req.category, str) or not req.category.strip():
        raise ValueError(f"VariationRequest.category debe ser str no-vacío, got {req.category!r}")
    if not isinstance(req.type, str) or not req.type.strip():
        raise ValueError(f"VariationRequest.type debe ser str no-vacío, got {req.type!r}")
    if req.category not in STANDARD_CATEGORIES:
        raise ValueError(
            f"VariationRequest.category={req.category!r} no está en "
            f"STANDARD_CATEGORIES={sorted(STANDARD_CATEGORIES)}"
        )
    # bool es subclase de int → excluir explícitamente.
    if isinstance(req.count, bool) or not isinstance(req.count, int):
        raise ValueError(f"VariationRequest.count debe ser int, got {type(req.count).__name__}")
    if req.count < 1:
        raise ValueError(f"VariationRequest.count debe ser >= 1, got {req.count!r}")
    if req.count > req.max_count:
        raise ValueError(f"VariationRequest.count={req.count} excede max_count={req.max_count}")
    if req.strategy not in ("seeded", "round_robin", "cartesian"):
        raise ValueError(
            f"VariationRequest.strategy desconocida: {req.strategy!r} "
            f"(esperado: 'seeded', 'round_robin', 'cartesian')"
        )
    for axis, options in req.base_variants.items():
        if not isinstance(axis, str) or not axis:
            raise ValueError(f"axis name debe ser str no-vacío, got {axis!r}")
        if not options:
            raise ValueError(f"axis {axis!r} debe tener al menos 1 opción (got 0)")
        for opt in options:
            if not isinstance(opt, str) or not opt:
                raise ValueError(f"axis {axis!r} tiene opción inválida: {opt!r}")


# =============================================================================
# EXPANSIÓN (combinatoria determinista)
# =============================================================================


def _cartesian(axes: Mapping[str, Sequence[str]]) -> list[dict[str, str]]:
    """Producto cartesiano de los ejes. Orden estable (ejes ordenados alfabéticamente).

    Axes vacío → ``[{}]`` (un único combo vacío). Esto garantiza que las
    estrategias tengan al menos 1 combo para ciclar.
    """
    if not axes:
        return [{}]
    keys = sorted(axes.keys())
    out: list[dict[str, str]] = [{}]
    for k in keys:
        opts = [str(o) for o in axes[k]]
        new_out: list[dict[str, str]] = []
        for base in out:
            for o in opts:
                nb = dict(base)
                nb[k] = o
                new_out.append(nb)
        out = new_out
    return out


def _variant_str_of(params: Mapping[str, str]) -> str:
    """Representación canónica de params: ``"axis1=v1|axis2=v2"`` (ordenada)."""
    return "|".join(f"{k}={v}" for k, v in sorted(params.items()))


def _rank_key(combo: dict[str, str], request_seed: int) -> tuple[int, str]:
    """Clave de ranking estable para la estrategia ``"seeded"``.

    Tupla ``(hash, variant_str)``: hash para diversidad, variant_str como
    tie-breaker determinista (estable entre procesos).
    """
    variant = _variant_str_of(combo)
    h = _stable_int(str(request_seed), variant)
    return (h, variant)


def _build_plan(req: VariationRequest) -> VariationPlan:
    """Construye el ``VariationPlan`` aplicando la estrategia elegida.

    Las tres estrategias comparten la misma forma de salida: ``count`` items
    con idx 0..count-1, cada uno con ``seed`` y ``variant_str`` deterministas.
    Solo difieren en el ORDEN de los combos cartesianos.
    """
    combos = _cartesian(req.base_variants)
    n_combos = len(combos)
    n = req.count

    if req.strategy == "seeded":
        request_seed = deterministic_seed(
            marca=req.marca,
            category=req.category,
            type=req.type,
            variant="__request__",
            idx=0,
            salt=req.seed_salt,
        )
        ranked = sorted(combos, key=lambda c: _rank_key(c, request_seed))
        # Offset desfasado por request_seed → distintos salts reordenan.
        offset = request_seed % max(1, n_combos)
        ordered = [ranked[(offset + i) % n_combos] for i in range(n)]
    elif req.strategy in ("round_robin", "cartesian"):
        # round_robin y cartesian son equivalentes cuando n_combos < n;
        # cuando n_combos >= n, ambos toman los primeros n en orden cartesiano.
        ordered = [combos[i % n_combos] for i in range(n)]
    else:
        # No debería llegar aquí: validate_request ya filtra.
        raise ValueError(f"strategy no soportada: {req.strategy!r}")

    variations: list[Variation] = []
    for i, params in enumerate(ordered):
        variant = _variant_str_of(params)
        seed = deterministic_seed(
            marca=req.marca,
            category=req.category,
            type=req.type,
            variant=variant,
            idx=i,
            salt=req.seed_salt,
        )
        variations.append(
            Variation(
                idx=i,
                seed=seed,
                params=tuple(sorted(params.items())),
                category=req.category,
                type=req.type,
                marca=req.marca,
                variant_str=variant,
            )
        )

    return VariationPlan(
        request=req,
        variations=tuple(variations),
        strategy_used=req.strategy,
    )


# =============================================================================
# API PÚBLICA
# =============================================================================


def expand_variations(
    count: int,
    category: str,
    type: str,
    base_variants: Mapping[str, Sequence[str]] | None = None,
    *,
    marca: str = "default",
    strategy: ExpansionStrategy = "seeded",
    seed_salt: str = "",
    locale: str = DEFAULT_LOCALE,
    palette_override: Mapping[str, str] | None = None,
    max_count: int = DEFAULT_MAX_COUNT,
    notes: str = "",
) -> VariationPlan:
    """Construye un ``VariationPlan`` determinista a partir de args posicionales.

    Función pura: mismos args → mismo plan. Sin I/O, sin ``time``, sin ``random``.

    Args:
        count:            Número exacto de variaciones a generar (``1..max_count``).
        category:         Una de ``STANDARD_CATEGORIES``.
        type:             Tipo de asset (p.ej. ``"lockup_horizontal"``).
        base_variants:    ``{axis_name: (opciones,)}``. Vacío/None → todas las
                          variations tienen ``params={}`` (solo ``idx``/``seed``
                          difieren).
        marca:            Slug de la marca (entra al seed).
        strategy:         ``"seeded"`` (default, mejor diversidad),
                          ``"round_robin"`` o ``"cartesian"``.
        seed_salt:        Sal opcional (entra al seed; cambia el plan).
        locale:           Locale passthrough (NO entra al seed).
        palette_override: Paleta opcional (passthrough, NO entra al seed).
        max_count:        Safety cap (default ``DEFAULT_MAX_COUNT`` = 200).
        notes:            Notas libres para trazabilidad.

    Raises:
        ValueError: Si algún campo no pasa ``validate_request``.

    Examples:
        >>> plan = expand_variations(
        ...     count=50, category="banners", type="ad_leaderboard",
        ...     base_variants={
        ...         "color": ("v1_color", "v2_mono", "v3_inverse"),
        ...         "layout": ("top", "middle", "bottom"),
        ...         "copy": ("short", "long"),
        ...     },
        ...     marca="prizma-iris", strategy="seeded",
        ... )
        >>> len(plan)
        50
    """
    req = VariationRequest(
        marca=marca,
        category=category,
        type=type,
        count=count,
        base_variants={k: tuple(v) for k, v in (base_variants or {}).items()},
        strategy=strategy,
        seed_salt=seed_salt,
        locale=locale,
        palette_override=dict(palette_override) if palette_override else None,
        max_count=max_count,
        notes=notes,
    )
    return plan_from_request(req)


def plan_from_request(req: VariationRequest) -> VariationPlan:
    """Atajo: valida y expande un ``VariationRequest`` pre-construido.

    Útil para callers que deserializan el request desde JSON, o que ya
    lo construyeron con kwargs nombrados.
    """
    validate_request(req)
    return _build_plan(req)


__all__ = [
    "DEFAULT_LOCALE",
    "DEFAULT_MAX_COUNT",
    "STANDARD_CATEGORIES",
    "ExpansionStrategy",
    "Variation",
    "VariationPlan",
    "VariationRequest",
    "__version__",
    "deterministic_seed",
    "expand_variations",
    "plan_from_request",
    "validate_request",
]
