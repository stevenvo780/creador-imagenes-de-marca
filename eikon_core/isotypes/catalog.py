"""Catálogo de 100 algoritmos de símbolo GENUINAMENTE distintos.

Cada entrada es una construcción matemática/geométrica DIFERENTE (no el mismo
algoritmo parametrizado). Un agente implementa cada `id` como una función
`gen_<id>(p: IsotypeParams) -> str` (SVG determinista por seed) en su pack.

Campos: (id, label_es, category, math_hint)
- id: snake_case, único; usado como valor del eje `isotype_style`.
- label_es: etiqueta clara para usuarios comunes (sin jerga).
- category: agrupación amigable en el wizard.
- math_hint: la idea matemática a implementar (guía para el generador).

Categorías visibles: Curvas · Espirales · Polígonos · Teselados · Fractales ·
Círculos · Ondas · Orgánico · Distribución · Tipográfico · Emblemas.
"""
from __future__ import annotations

# (id, label_es, category, math_hint)
ALGORITHMS: list[tuple[str, str, str, str]] = [
    # ── Curvas paramétricas ──────────────────────────────────────────────────
    ("lissajous", "Curva de Lissajous", "Curvas", "x=sin(a·t+δ), y=sin(b·t); a,b,δ por seed"),
    ("rosa_polar", "Rosa polar", "Curvas", "r=cos(k·θ); k pétalos por seed"),
    ("espirografo", "Espirógrafo", "Curvas", "hipotrocoide: punto en círculo rodando dentro de otro"),
    ("epitrocoide", "Epitrocoide", "Curvas", "punto en círculo rodando por fuera de otro"),
    ("superelipse", "Superelipse", "Curvas", "|x/a|^n+|y/b|^n=1; n por seed"),
    ("superformula", "Superfórmula", "Curvas", "Gielis: r(θ)=(|cos(mθ/4)/a|^n2+|sin(mθ/4)/b|^n3)^(-1/n1)"),
    ("cardioide", "Cardioide", "Curvas", "r=1−cos θ (acotada por epicicloide de 1 cúspide)"),
    ("lemniscata", "Lemniscata", "Curvas", "r²=cos(2θ) (figura de 8)"),
    ("astroide", "Astroide", "Curvas", "x=cos³t, y=sin³t"),
    ("nefroide", "Nefroide", "Curvas", "epicicloide de 2 cúspides"),
    ("deltoide", "Deltoide", "Curvas", "hipocicloide de 3 cúspides"),
    ("mariposa", "Curva mariposa", "Curvas", "r=e^{cosθ}−2cos4θ+sin^5(θ/12)"),
    ("corazon", "Curva de corazón", "Curvas", "x=16sin³t, y=13cos t−5cos2t−2cos3t−cos4t"),
    ("hipocicloide", "Hipocicloide", "Curvas", "círculo rodando dentro; k cúspides por seed"),
    ("epicicloide", "Epicicloide", "Curvas", "círculo rodando por fuera; k cúspides por seed"),

    # ── Espirales ────────────────────────────────────────────────────────────
    ("espiral_arquimedes", "Espiral de Arquímedes", "Espirales", "r=a·θ (paso constante)"),
    ("espiral_logaritmica", "Espiral logarítmica", "Espirales", "r=a·e^{bθ}"),
    ("espiral_fermat", "Espiral de Fermat", "Espirales", "r=±√θ (dos brazos)"),
    ("espiral_aurea", "Espiral áurea", "Espirales", "crecimiento por φ cada cuarto de vuelta"),
    ("clotoide", "Espiral de Euler", "Espirales", "clotoide: curvatura ∝ longitud (integrales de Fresnel)"),
    ("espiral_hiperbolica", "Espiral hiperbólica", "Espirales", "r=a/θ"),
    ("doble_espiral", "Doble espiral", "Espirales", "dos espirales opuestas (yin-yang lineal)"),
    ("espiral_cuadrada", "Espiral cuadrada", "Espirales", "espiral por segmentos en ángulo recto"),

    # ── Polígonos y estrellas ─────────────────────────────────────────────────
    ("poligono_regular", "Polígono regular", "Polígonos", "n lados; n por seed"),
    ("estrella_np", "Estrella de n puntas", "Polígonos", "polígono estrellado {n/k}"),
    ("poligonos_anidados", "Polígonos anidados", "Polígonos", "k polígonos concéntricos decrecientes"),
    ("poligonos_rotados", "Polígonos en capas", "Polígonos", "mismo polígono rotado en cada capa"),
    ("reuleaux", "Triángulo de Reuleaux", "Polígonos", "polígono de ancho constante (arcos)"),
    ("estrella_rafaga", "Ráfaga de estrella", "Polígonos", "rayos alternando largo desde el centro"),
    ("poligono_espiral", "Espiral de polígonos", "Polígonos", "polígonos rotando y encogiendo (vórtice)"),
    ("triangulos_radiales", "Triángulos radiales", "Polígonos", "n triángulos apuntando al centro"),
    ("zigzag_radial", "Zigzag radial", "Polígonos", "polígono dentado (zigzag) alrededor"),
    ("corona_picos", "Corona de picos", "Polígonos", "anillo de picos triangulares"),

    # ── Teselados y retículas ────────────────────────────────────────────────
    ("truchet", "Mosaico de Truchet", "Teselados", "celdas con arcos/diagonales orientados al azar"),
    ("penrose", "Teselado de Penrose", "Teselados", "rombos aperiódicos (deflación P3)"),
    ("retícula_hexagonal", "Retícula hexagonal", "Teselados", "panal de hexágonos"),
    ("retícula_triangular", "Retícula triangular", "Teselados", "malla de triángulos"),
    ("voronoi", "Diagrama de Voronoi", "Teselados", "celdas de proximidad de puntos seeded"),
    ("delaunay", "Triangulación de Delaunay", "Teselados", "triangulación de puntos seeded"),
    ("empaque_circulos", "Empaque de círculos", "Teselados", "círculos de radios variados sin solapar"),
    ("patron_islamico", "Patrón islámico", "Teselados", "estrella-y-polígono girih"),
    ("espiga", "Espiga", "Teselados", "rectángulos en patrón herringbone"),
    ("molinete", "Molinete", "Teselados", "teselado pinwheel (triángulos rotados)"),
    ("cairo", "Teselado de El Cairo", "Teselados", "pentágonos de El Cairo"),
    ("ammann", "Teselado de Ammann", "Teselados", "Ammann–Beenker octagonal aperiódico"),

    # ── Fractales ──────────────────────────────────────────────────────────────
    ("sierpinski_triangulo", "Triángulo de Sierpinski", "Fractales", "recursión de triángulos"),
    ("sierpinski_alfombra", "Alfombra de Sierpinski", "Fractales", "recursión de cuadrados 3×3"),
    ("koch", "Copo de Koch", "Fractales", "curva de Koch en triángulo base"),
    ("dragon", "Curva del dragón", "Fractales", "L-system: plegado de papel"),
    ("hilbert", "Curva de Hilbert", "Fractales", "curva de llenado de espacio"),
    ("gosper", "Curva de Gosper", "Fractales", "curva de llenado hexagonal (flowsnake)"),
    ("levy", "Curva C de Lévy", "Fractales", "L-system de ángulo 45°"),
    ("t_cuadrado", "Fractal T-cuadrado", "Fractales", "cuadrados recursivos en esquinas"),
    ("vicsek", "Fractal de Vicsek", "Fractales", "recursión en cruz 3×3"),
    ("arbol_pitagoras", "Árbol de Pitágoras", "Fractales", "cuadrados ramificándose en ángulo"),
    ("h_arbol", "Árbol H", "Fractales", "recursión de H que se encogen"),
    ("gasket_apolonio", "Empaque de Apolonio", "Fractales", "círculos tangentes recursivos"),

    # ── Orgánico / ramificación / sistemas ────────────────────────────────────
    ("planta_lsystem", "Planta (L-system)", "Orgánico", "L-system con regla F→F[+F]F[-F]F"),
    ("arbol_ramificado", "Árbol ramificado", "Orgánico", "ramas recursivas con ángulo/encogimiento seeded"),
    ("helecho", "Helecho de Barnsley", "Orgánico", "IFS de 4 transformaciones afines"),
    ("metaballs", "Metabolas", "Orgánico", "isocontorno de suma de campos radiales"),
    ("blob_organico", "Forma orgánica", "Orgánico", "polígono radial suavizado con Bézier y ruido seeded"),
    ("flujo_campo", "Líneas de flujo", "Orgánico", "streamlines siguiendo un campo vectorial seeded"),
    ("reaccion_difusion", "Reacción-difusión", "Orgánico", "patrón de Turing simplificado (manchas)"),
    ("automata_r30", "Autómata regla 30", "Orgánico", "autómata celular 1D apilado"),
    ("game_of_life", "Vida de Conway", "Orgánico", "instantánea de Game of Life seeded"),
    ("grietas", "Grietas", "Orgánico", "Voronoi craquelado (bordes de celdas)"),

    # ── Círculos / geometría sagrada ──────────────────────────────────────────
    ("flor_vida", "Flor de la vida", "Círculos", "círculos en retícula hexagonal solapados"),
    ("semilla_vida", "Semilla de la vida", "Círculos", "7 círculos (central + 6)"),
    ("vesica", "Vesica piscis", "Círculos", "intersección de dos círculos"),
    ("anillos_borromeos", "Anillos borromeos", "Círculos", "3 anillos entrelazados"),
    ("triquetra", "Triquetra", "Círculos", "3 vesicas entrelazadas (nudo trinitario)"),
    ("circulos_concentricos", "Círculos concéntricos", "Círculos", "anillos con grosores variados"),
    ("venn", "Círculos superpuestos", "Círculos", "n círculos en anillo (estilo Venn)"),
    ("metatron", "Cubo de Metatrón", "Círculos", "13 círculos + líneas conectoras"),
    ("roseta", "Rosetón", "Círculos", "pétalos por compás (arcos radiales)"),
    ("mandala", "Mandala", "Círculos", "simetría radial de n sectores con motivos"),

    # ── Ondas / campos ──────────────────────────────────────────────────────────
    ("interferencia", "Interferencia de ondas", "Ondas", "suma de dos frentes de onda circulares"),
    ("ondas_concentricas", "Ondas concéntricas", "Ondas", "anillos sinusoidales desde el centro"),
    ("chladni", "Patrón de Chladni", "Ondas", "líneas nodales de placa vibrante (cos·cos)"),
    ("moire", "Patrón de muaré", "Ondas", "dos retículas superpuestas con leve giro"),
    ("lineas_contorno", "Líneas de contorno", "Ondas", "isolíneas de un campo de altura seeded"),
    ("bandas_seno", "Bandas sinusoidales", "Ondas", "franjas onduladas paralelas"),
    ("campo_dipolo", "Campo dipolo", "Ondas", "líneas de campo de dos cargas opuestas"),
    ("remolino", "Remolino", "Ondas", "líneas curvándose alrededor de un vórtice"),
    ("ondas_radiales", "Ondas radiales", "Ondas", "rayos sinusoidales desde el centro"),
    ("trenza_ondas", "Trenza de ondas", "Ondas", "dos senos desfasados que se trenzan"),

    # ── Distribución / empaquetado ─────────────────────────────────────────────
    ("filotaxis", "Filotaxis (girasol)", "Distribución", "espiral de Vogel con ángulo áureo 137.5°"),
    ("puntos_aureos", "Puntos en ángulo áureo", "Distribución", "puntos a 137.5° con radio creciente"),
    ("poisson", "Puntos dispersos", "Distribución", "muestreo tipo Poisson-disk (mín. distancia)"),
    ("trama_puntos", "Trama de puntos", "Distribución", "halftone: puntos de tamaño según radio"),
    ("degradado_puntos", "Degradado de puntos", "Distribución", "retícula de puntos con tamaño en gradiente"),
    ("constelacion", "Constelación", "Distribución", "puntos seeded unidos por aristas cercanas"),

    # ── Tipográfico ──────────────────────────────────────────────────────────
    ("monograma", "Monograma", "Tipográfico", "inicial sobre forma; capas a dos colores"),
    ("letra_negativa", "Letra en negativo", "Tipográfico", "inicial recortada de una forma sólida"),
    ("letra_stencil", "Letra stencil", "Tipográfico", "inicial con cortes tipo plantilla"),
    ("ligadura", "Ligadura de iniciales", "Tipográfico", "dos iniciales entrelazadas"),
    ("inicial_circulo", "Inicial en círculo", "Tipográfico", "inicial centrada con texto circular alrededor"),

    # ── Emblemas ─────────────────────────────────────────────────────────────
    ("escudo", "Escudo", "Emblemas", "blasón (forma de escudo) con división heráldica"),
    ("sello", "Sello circular", "Emblemas", "anillo doble con dentado y centro"),
    ("laurel", "Corona de laurel", "Emblemas", "dos ramas curvas con hojas"),
    ("banderin", "Banderín", "Emblemas", "cinta/banner con cola en V"),
]


def by_category() -> dict[str, list[tuple[str, str, str, str]]]:
    """Agrupa el catálogo por categoría (para el wizard)."""
    out: dict[str, list[tuple[str, str, str, str]]] = {}
    for entry in ALGORITHMS:
        out.setdefault(entry[2], []).append(entry)
    return out
