"""
styles.py
Sistema de diseno centralizado del dashboard.

Rediseno visual (v2) sobre la paleta de marca:
    #FFF1E7  crema      -> lienzo / fondo de pagina
    #B5D2E6  azul niebla-> acentos suaves, rellenos, tracks
    #326080  azul hondo -> tinta principal, superficies oscuras, titulos
    #805232  tierra     -> acento calido, regimen de crisis

Las variantes cromaticas de los colores de datos (CALMA / CRISIS y la paleta
cualitativa de activos) son versiones con mas croma de esos mismos tonos: la
paleta de marca es deliberadamente desaturada y, usada tal cual en marcas finas
(lineas de 2px, celdas, barras), no supera los umbrales de separacion para
daltonismo. Todos los sets de color de este archivo estan validados con el
validador de paletas (banda de luminosidad, piso de croma, separacion CVD
deutan/protan/tritan y contraste contra el lienzo).

Uso en app.py:
    import styles
    styles.inject_global_css()
    with styles.card("overview-hero", variant="dark"):
        styles.hero_metric("38.2", "VIX ACTUAL")
"""

from contextlib import contextmanager

import streamlit as st

# --- Paleta de marca ---------------------------------------------------------
CREAM = "#FFF1E7"   # lienzo
MIST = "#B5D2E6"    # azul niebla
DEEP = "#326080"    # azul hondo
CLAY = "#805232"    # tierra

# --- Derivados de superficie y tinta ----------------------------------------
CARD_BG = "#FFFFFF"
CARD_BG_ALT = "#FDF7F2"
CARD_DARK_BG = DEEP
BG_GRAD_START = "#FFF7F1"
BG_GRAD_END = CREAM
SIDEBAR_BG = "#FBEADF"

INK = "#22384A"            # texto principal
TEXT_MUTED = "#7A8896"     # texto secundario
GRID = "#E9DCD1"           # rejilla calida, recesiva
HAIRLINE = "#EFE1D6"       # bordes de 1px

# --- Colores de datos --------------------------------------------------------
# Par de regimen (categorico de 2): azul = Calma, tierra = Crisis.
# Misma familia que DEEP/CLAY, con croma suficiente para pasar CVD.
CALMA = "#2472A6"
CRISIS = "#A85E24"
CALMA_SOFT = "rgba(36, 114, 166, 0.12)"
CRISIS_SOFT = "rgba(168, 94, 36, 0.13)"

# Aliases retro-compatibles con el codigo previo.
NAVY = DEEP
TEAL = CALMA
RED = CRISIS
AMBER = "#B99012"

# Escala divergente para correlacion: frio (-1) -> neutro (0) -> calido (+1).
# Dos tonos + punto medio neutro; +1 (todo se mueve junto = la tesis) es el
# extremo calido/alarmante, -1 (cobertura real) el extremo frio.
ESCALA_CORR = [
    [0.00, "#12496E"],
    [0.15, "#2472A6"],
    [0.32, "#7FB0D0"],
    [0.46, "#CFE0EC"],
    [0.50, "#F4EFEA"],
    [0.54, "#EDD9C6"],
    [0.68, "#D6A170"],
    [0.85, "#A85E24"],
    [1.00, "#6E3B12"],
]

# Escala secuencial de una sola tinta (magnitud, sin polaridad).
ESCALA_SEC = [
    [0.0, "#FFF1E7"],
    [0.25, "#DCE9F2"],
    [0.5, "#B5D2E6"],
    [0.75, "#5C93B8"],
    [1.0, "#1C4C6B"],
]

# Paleta cualitativa de activos (orden fijo, nunca ciclado por seleccion).
# Validada: banda de luminosidad OK, croma OK, peor par adyacente CVD OK,
# piso de vision normal OK. Los 3 tonos con contraste < 3:1 contra el crema
# (dorado, oliva, rosa) siempre viajan con leyenda + etiqueta directa + tabla.
PALETA_ACTIVOS = [
    "#1668A5",  # azul senal
    "#B05A1E",  # tierra quemada
    "#0E8F80",  # verde azulado
    "#8A4A86",  # ciruela
    "#B99012",  # dorado
    "#4756A8",  # indigo
    "#BE3B34",  # arcilla roja
    "#7D9B1F",  # oliva
    "#D0739A",  # rosa palo
    "#6A4CA8",  # violeta
]

FONT_SERIF = "Georgia, Cambria, 'Times New Roman', serif"
FONT_SANS = "'Inter', 'Calibri', 'Segoe UI', sans-serif"

# Color FIJO por activo (no depende del orden de seleccion): imprescindible para el
# resaltado enlazado -- un mismo activo mantiene su color en las 6 vistas.
ORDEN_ACTIVOS = ["SPY", "QQQ", "TLT", "GLD", "HYG", "VNQ", "EEM", "DBC", "UUP", "BTC-USD"]
COLOR_ACTIVO = {a: PALETA_ACTIVOS[i % len(PALETA_ACTIVOS)] for i, a in enumerate(ORDEN_ACTIVOS)}


def color_activo(activo: str) -> str:
    """Color estable de un activo; cae a la paleta ciclica si es uno desconocido."""
    return COLOR_ACTIVO.get(activo, PALETA_ACTIVOS[abs(hash(activo)) % len(PALETA_ACTIVOS)])


PLOTLY_TRANSPARENT = dict(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")

# Layout base compartido por todas las figuras: tipografia, ejes recesivos,
# hover con la misma piel que las cards.
PLOTLY_BASE = dict(
    **PLOTLY_TRANSPARENT,
    font=dict(family=FONT_SANS, color=INK, size=12),
    hoverlabel=dict(
        bgcolor="rgba(255,255,255,0.96)",
        bordercolor=HAIRLINE,
        font=dict(family=FONT_SANS, color=INK, size=12),
    ),
    colorway=PALETA_ACTIVOS,
)


def eje(**kwargs):
    """Eje recesivo por defecto: rejilla calida fina, sin linea de eje dura."""
    base = dict(
        gridcolor=GRID,
        gridwidth=1,
        zeroline=False,
        showline=False,
        ticks="outside",
        ticklen=4,
        tickcolor=GRID,
        tickfont=dict(size=11, color=TEXT_MUTED),
        title_font=dict(size=12, color=TEXT_MUTED),
    )
    base.update(kwargs)
    return base


def _css():
    return f"""
<style>
.stApp {{
  background: linear-gradient(168deg, {BG_GRAD_START} 0%, {BG_GRAD_END} 46%, #F7E3D6 100%);
}}
.stApp, .stApp p, .stApp li, .stApp label {{ color: {INK}; }}

/* Respiracion general: el aire es parte del diseno */
.block-container {{ padding-top: 2.2rem !important; max-width: 1500px; }}

section[data-testid="stSidebar"] {{
  background: {SIDEBAR_BG};
  border-right: 1px solid {HAIRLINE};
}}
section[data-testid="stSidebar"] h2 {{
  font-family: {FONT_SERIF};
  color: {DEEP};
  letter-spacing: -0.01em;
}}

/* --- Barra superior: st.container(key="topbar", horizontal=True) -------- */
div[class*="st-key-topbar"] {{
  background: linear-gradient(120deg, {DEEP} 0%, #27506C 100%);
  border-radius: 999px !important;
  padding: 0.55rem 1.5rem;
  margin-bottom: 1.6rem;
  box-shadow: 0 10px 30px rgba(50, 96, 128, 0.22);
  justify-content: space-between !important;
  align-items: center !important;
  border: none !important;
}}
.topbar-title {{
  font-family: {FONT_SERIF};
  color: {CREAM};
  font-size: 1.18rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  white-space: nowrap;
}}
.topbar-title .accent {{ color: {MIST}; font-weight: 400; }}
.topbar-sub {{
  font-family: {FONT_SANS};
  color: rgba(255, 241, 231, 0.62);
  font-size: 0.78rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  text-align: right;
  white-space: nowrap;
}}
/* el segmented_control vive dentro del topbar azul: fondo/track translucido */
div[class*="st-key-topbar"] div[class*="st-key-nav_tab"] {{
  background: rgba(181, 210, 230, 0.14);
  border-radius: 999px;
  padding: 0.2rem;
}}
div[class*="st-key-topbar"] button p {{ color: rgba(255,241,231,0.85) !important; }}
div[class*="st-key-topbar"] button[aria-checked="true"] {{
  background: {CREAM} !important;
}}
div[class*="st-key-topbar"] button[aria-checked="true"] p {{ color: {DEEP} !important; font-weight: 700; }}

/* --- Cards: st.container(key=f"card-{{variant}}-{{name}}", border=True) -- */
div[class*="st-key-card-light-"] {{
  background: {CARD_BG};
  border-radius: 1.5rem !important;
  border: 1px solid {HAIRLINE} !important;
  box-shadow: 0 1px 2px rgba(50, 96, 128, 0.04), 0 14px 38px rgba(50, 96, 128, 0.07);
  padding: 1.35rem 1.5rem;
  position: relative;
  overflow: hidden;
}}
div[class*="st-key-card-soft-"] {{
  background: {CARD_BG_ALT};
  border-radius: 1.5rem !important;
  border: 1px solid {HAIRLINE} !important;
  box-shadow: 0 10px 30px rgba(50, 96, 128, 0.05);
  padding: 1.35rem 1.5rem;
  position: relative;
  overflow: hidden;
}}
div[class*="st-key-card-dark-"] {{
  background: linear-gradient(150deg, {DEEP} 0%, #29506B 100%);
  border-radius: 1.5rem !important;
  border: none !important;
  box-shadow: 0 14px 38px rgba(50, 96, 128, 0.28);
  padding: 1.35rem 1.5rem;
  position: relative;
  overflow: hidden;
}}
div[class*="st-key-card-dark-"], div[class*="st-key-card-dark-"] * {{
  color: {CREAM} !important;
}}
div[class*="st-key-card-mvp-"] {{
  background: {CARD_BG};
  border-radius: 1.5rem !important;
  border: 1px solid {HAIRLINE} !important;
  border-top: 3px solid {CLAY} !important;
  box-shadow: 0 14px 38px rgba(128, 82, 50, 0.10);
  padding: 1.35rem 1.5rem;
  position: relative;
  overflow: hidden;
}}

/* --- Icono de esquina ---------------------------------------------------- */
.icon-corner {{
  position: absolute;
  top: 1.15rem;
  right: 1.4rem;
  font-size: 1rem;
  color: {MIST};
  opacity: 0.9;
}}
div[class*="st-key-card-dark-"] .icon-corner {{ color: rgba(181,210,230,0.7); }}

/* --- Badges / pills ------------------------------------------------------ */
.badge {{
  display: inline-block;
  font-family: {FONT_SANS};
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  padding: 0.22rem 0.7rem;
  border-radius: 999px;
  margin-left: 0.5rem;
  vertical-align: middle;
  white-space: nowrap;
}}
.badge-dark  {{ background: {DEEP}; color: {CREAM}; }}
.badge-red   {{ background: rgba(168, 94, 36, 0.14); color: {CLAY}; }}
.badge-teal  {{ background: rgba(36, 114, 166, 0.13); color: {CALMA}; }}
.badge-amber {{ background: rgba(185, 144, 18, 0.16); color: #7C5F06; }}
.badge-mist  {{ background: {MIST}; color: {DEEP}; }}

/* --- Hero metrics -------------------------------------------------------- */
.hero-label {{
  font-family: {FONT_SANS};
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: {TEXT_MUTED};
  margin-bottom: 0.25rem;
}}
div[class*="st-key-card-dark-"] .hero-label {{ color: rgba(181,210,230,0.85) !important; }}
.hero-value {{
  font-family: {FONT_SERIF};
  font-size: 2.25rem;
  font-weight: 700;
  line-height: 1.05;
  letter-spacing: -0.02em;
  color: {DEEP};
  font-variant-numeric: tabular-nums;
}}
div[class*="st-key-card-dark-"] .hero-value {{ color: {CREAM} !important; }}
.hero-sub {{
  font-family: {FONT_SANS};
  font-size: 0.76rem;
  color: {TEXT_MUTED};
  margin-top: 0.3rem;
  line-height: 1.35;
}}
div[class*="st-key-card-dark-"] .hero-sub {{ color: rgba(181,210,230,0.8) !important; }}

/* --- Progress pill ------------------------------------------------------- */
.progress-track {{
  background: rgba(50, 96, 128, 0.10);
  border-radius: 999px;
  height: 0.42rem;
  width: 100%;
  overflow: hidden;
  margin-top: 0.6rem;
}}
div[class*="st-key-card-dark-"] .progress-track {{ background: rgba(255,241,231,0.20); }}
.progress-fill {{ height: 100%; border-radius: 999px; }}

/* --- Callout / nota ------------------------------------------------------ */
.callout {{
  font-family: {FONT_SANS};
  font-size: 0.82rem;
  line-height: 1.55;
  color: #4C5E6E;
  background: rgba(181, 210, 230, 0.20);
  border-left: 3px solid {MIST};
  border-radius: 0 0.7rem 0.7rem 0;
  padding: 0.7rem 0.95rem;
  margin-top: 0.7rem;
}}
.callout b {{ color: {DEEP}; }}

/* --- Lectura guiada (descripciones parametrizadas) ----------------------- */
.lectura {{
  font-family: {FONT_SANS};
  background: linear-gradient(180deg, #FDF7F2 0%, {CREAM} 100%);
  border: 1px solid {HAIRLINE};
  border-radius: 1.1rem;
  padding: 1rem 1.2rem;
  margin: 0.2rem 0 0.9rem 0;
}}
.lectura-eyebrow {{
  font-size: 0.64rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: {CLAY};
  margin-bottom: 0.4rem;
}}
.lectura-lead {{
  font-family: {FONT_SERIF};
  font-size: 1.02rem;
  line-height: 1.5;
  color: {DEEP};
  margin-bottom: 0.55rem;
}}
.lectura ul {{ margin: 0; padding-left: 1.05rem; }}
.lectura li {{
  font-size: 0.855rem;
  line-height: 1.6;
  color: #4C5E6E;
  margin-bottom: 0.22rem;
}}
.lectura li::marker {{ color: {MIST}; }}
.lectura b, .lectura strong {{ color: {DEEP}; font-weight: 600; }}
.lectura .num {{
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  color: {CLAY};
}}

/* --- Titulo de seccion --------------------------------------------------- */
.section-title {{
  font-family: {FONT_SERIF};
  font-size: 1.22rem;
  font-weight: 700;
  letter-spacing: -0.015em;
  color: {DEEP};
  margin-bottom: 0.2rem;
}}
div[class*="st-key-card-dark-"] .section-title {{ color: {CREAM} !important; }}
.section-caption {{
  font-family: {FONT_SANS};
  font-size: 0.845rem;
  line-height: 1.55;
  color: {TEXT_MUTED};
  margin-bottom: 0.85rem;
  max-width: 78ch;
}}

/* --- Regla fina de separacion -------------------------------------------- */
.rule {{
  border: none;
  border-top: 1px solid {HAIRLINE};
  margin: 1.6rem 0 1.1rem 0;
}}

/* --- Bloque de self-report ------------------------------------------------ */
div[class*="st-key-card-report-"] {{
  background: linear-gradient(120deg, {DEEP} 0%, #2A536F 62%, #4C4030 100%);
  border-radius: 1.5rem !important;
  border: none !important;
  box-shadow: 0 14px 38px rgba(50, 96, 128, 0.26);
  padding: 1.35rem 1.6rem;
}}
div[class*="st-key-card-report-"], div[class*="st-key-card-report-"] * {{ color: {CREAM} !important; }}
div[class*="st-key-card-report-"] .section-caption {{ color: rgba(255,241,231,0.72) !important; }}
div[class*="st-key-card-report-"] button {{
  background: {CREAM} !important;
  border: none !important;
  font-weight: 700 !important;
}}
div[class*="st-key-card-report-"] button p {{ color: {DEEP} !important; }}
div[class*="st-key-card-report-"] button:hover {{ background: {MIST} !important; }}

/* --- Tablas -------------------------------------------------------------- */
div[data-testid="stDataFrame"] {{
  border-radius: 0.9rem;
  overflow: hidden;
  border: 1px solid {HAIRLINE};
}}

/* --- Pie de pagina ------------------------------------------------------- */
.stCaption, div[data-testid="stCaptionContainer"] p {{ color: {TEXT_MUTED} !important; }}
</style>
"""


def inject_global_css():
    st.markdown(_css(), unsafe_allow_html=True)


@contextmanager
def card(name: str, variant: str = "light"):
    """Card reutilizable. variant: 'light' | 'soft' | 'dark' | 'mvp' | 'report'."""
    with st.container(key=f"card-{variant}-{name}", border=True):
        yield


def section_title(text: str, caption: str = "", badge_html: str = ""):
    st.markdown(
        f'<div class="section-title">{text}{badge_html}</div>'
        + (f'<div class="section-caption">{caption}</div>' if caption else ""),
        unsafe_allow_html=True,
    )


def badge(text: str, variant: str = "dark") -> str:
    return f'<span class="badge badge-{variant}">{text}</span>'


def icon_corner(icon: str = "↗"):
    st.markdown(f'<div class="icon-corner">{icon}</div>', unsafe_allow_html=True)


def hero_metric(value: str, label: str, sub: str = "", color: str = None):
    color_style = f'style="color:{color}"' if color else ""
    st.markdown(
        f'<div class="hero-label">{label}</div>'
        f'<div class="hero-value" {color_style}>{value}</div>'
        + (f'<div class="hero-sub">{sub}</div>' if sub else ""),
        unsafe_allow_html=True,
    )


def note(html: str):
    """Callout sobrio para notas de limitaciones/accesibilidad dentro de una card."""
    st.markdown(f'<div class="callout">{html}</div>', unsafe_allow_html=True)


def rule():
    st.markdown('<hr class="rule">', unsafe_allow_html=True)


def progress_pill(pct: float, color: str = CLAY):
    pct = max(0.0, min(100.0, pct))
    st.markdown(
        f'<div class="progress-track"><div class="progress-fill" '
        f'style="width:{pct:.0f}%; background:{color};"></div></div>',
        unsafe_allow_html=True,
    )


def lectura(eyebrow: str, lead: str, puntos: list):
    """Bloque de 'lectura guiada': la descripcion parametrizada de un grafico.

    eyebrow -- etiqueta corta ("COMO LEER ESTE GRAFICO").
    lead    -- frase principal, ya resuelta con los activos/regimen en pantalla.
    puntos  -- lista de bullets en HTML (pueden traer <b> y <span class="num">).
    """
    items = "".join(f"<li>{p}</li>" for p in puntos)
    st.markdown(
        f'<div class="lectura">'
        f'<div class="lectura-eyebrow">{eyebrow}</div>'
        f'<div class="lectura-lead">{lead}</div>'
        f'<ul>{items}</ul>'
        f'</div>',
        unsafe_allow_html=True,
    )
