"""
styles.py
Sistema de diseno centralizado del dashboard: paleta, tipografia, CSS de cards/nav/badges
y helpers reutilizables para que cada vista (Overview, Volatilidad, Correlacion, y las que
se agreguen en Fase C) comparta el mismo lenguaje visual.

Uso en app.py:
    import styles
    styles.inject_global_css()
    with styles.card("overview-hero", variant="dark"):
        styles.hero_metric("38.2", "VIX ACTUAL")
"""

from contextlib import contextmanager

import streamlit as st

# --- Paleta ------------------------------------------------------------------
NAVY = "#1A2B4A"
TEAL = "#2E86AB"
RED = "#C0392B"
AMBER = "#F2C14E"
CARD_BG = "#FFFFFF"
CARD_BG_ALT = "#FBF9F5"
CARD_DARK_BG = "#1A2B4A"
GRID = "#E4DFC9"
TEXT_MUTED = "#5B6B82"
BG_GRAD_START = "#F2F1EF"
BG_GRAD_END = "#FBF4DC"

FONT_SERIF = "Georgia, Cambria, 'Times New Roman', serif"
FONT_SANS = "'Inter', 'Calibri', 'Segoe UI', sans-serif"

# Paleta cualitativa para hasta 11 activos (ancla navy/teal/rojo/ambar + extension
# distinguible, evitando el par rojo-verde clasico que confunde a deuteranopes).
PALETA_ACTIVOS = [
    "#1A2B4A", "#2E86AB", "#C0392B", "#F2C14E", "#6C8EBF",
    "#8E5572", "#A6A15C", "#8C5A3C", "#7FB3D5", "#4A4A4A", "#E08283",
]

# Color FIJO por activo (no depende del orden de seleccion): imprescindible para el
# resaltado enlazado -- un mismo activo mantiene su color en las 5 vistas.
ORDEN_ACTIVOS = ["SPY", "QQQ", "TLT", "GLD", "HYG", "VNQ", "EEM", "DBC", "UUP", "BTC-USD"]
COLOR_ACTIVO = {a: PALETA_ACTIVOS[i % len(PALETA_ACTIVOS)] for i, a in enumerate(ORDEN_ACTIVOS)}


def color_activo(activo: str) -> str:
    """Color estable de un activo; cae a la paleta ciclica si es uno desconocido."""
    return COLOR_ACTIVO.get(activo, PALETA_ACTIVOS[abs(hash(activo)) % len(PALETA_ACTIVOS)])


PLOTLY_TRANSPARENT = dict(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")


def _css():
    return f"""
<style>
.stApp {{
  background: linear-gradient(135deg, {BG_GRAD_START} 0%, {BG_GRAD_END} 100%);
}}

/* --- Barra superior: st.container(key="topbar", horizontal=True) -------- */
div[class*="st-key-topbar"] {{
  background: {CARD_DARK_BG};
  border-radius: 999px !important;
  padding: 0.6rem 1.6rem;
  margin-bottom: 1.4rem;
  box-shadow: 0 8px 24px rgba(26, 43, 74, 0.18);
  justify-content: space-between !important;
  align-items: center !important;
}}
.topbar-title {{
  font-family: {FONT_SERIF};
  color: white;
  font-size: 1.15rem;
  font-weight: 700;
  white-space: nowrap;
}}
.topbar-sub {{
  font-family: {FONT_SANS};
  color: rgba(255,255,255,0.65);
  font-size: 0.82rem;
  text-align: right;
  white-space: nowrap;
}}
/* el segmented_control vive dentro del topbar navy: fondo/track transparente */
div[class*="st-key-topbar"] div[class*="st-key-nav_tab"] {{
  background: rgba(255,255,255,0.08);
  border-radius: 999px;
  padding: 0.2rem;
}}

/* --- Cards: st.container(key=f"card-{{variant}}-{{name}}", border=True) -- */
div[class*="st-key-card-light-"] {{
  background: {CARD_BG};
  border-radius: 1.4rem !important;
  box-shadow: 0 8px 30px rgba(26, 43, 74, 0.08);
  padding: 1.2rem 1.4rem;
  position: relative;
  overflow: hidden;
}}
div[class*="st-key-card-dark-"] {{
  background: {CARD_DARK_BG};
  border-radius: 1.4rem !important;
  box-shadow: 0 8px 30px rgba(26, 43, 74, 0.22);
  padding: 1.2rem 1.4rem;
  position: relative;
  overflow: hidden;
}}
div[class*="st-key-card-dark-"], div[class*="st-key-card-dark-"] * {{
  color: #F2F1EF !important;
}}
div[class*="st-key-card-mvp-"] {{
  background: {CARD_BG};
  border-radius: 1.4rem !important;
  box-shadow: 0 0 0 3px rgba(192, 57, 43, 0.12), 0 8px 30px rgba(26, 43, 74, 0.08);
  border-color: {RED} !important;
  border-width: 2px !important;
  padding: 1.2rem 1.4rem;
  position: relative;
  overflow: hidden;
}}

/* --- Icono de esquina (estilo "Progress ↗") ----------------------------- */
.icon-corner {{
  position: absolute;
  top: 1.1rem;
  right: 1.3rem;
  font-size: 1.1rem;
  color: {TEXT_MUTED};
  opacity: 0.7;
}}

/* --- Badges / pills ------------------------------------------------------ */
.badge {{
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  padding: 0.2rem 0.65rem;
  border-radius: 999px;
  margin-left: 0.5rem;
  vertical-align: middle;
}}
.badge-dark {{ background: {NAVY}; color: white; }}
.badge-red {{ background: {RED}; color: white; }}
.badge-teal {{ background: {TEAL}; color: white; }}
.badge-amber {{ background: {AMBER}; color: {NAVY}; }}

/* --- Hero metrics (numero grande + label chico en mayusculas) ----------- */
.hero-label {{
  font-family: {FONT_SANS};
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: {TEXT_MUTED};
  margin-bottom: 0.15rem;
}}
div[class*="st-key-card-dark-"] .hero-label {{ color: #C7D2E0; }}
.hero-value {{
  font-family: {FONT_SERIF};
  font-size: 2.1rem;
  font-weight: 700;
  line-height: 1.1;
}}
.hero-sub {{
  font-family: {FONT_SANS};
  font-size: 0.78rem;
  color: {TEXT_MUTED};
  margin-top: 0.2rem;
}}
div[class*="st-key-card-dark-"] .hero-sub {{ color: #C7D2E0; }}

/* --- Progress pill -------------------------------------------------------- */
.progress-track {{
  background: rgba(26, 43, 74, 0.08);
  border-radius: 999px;
  height: 0.55rem;
  width: 100%;
  overflow: hidden;
  margin-top: 0.5rem;
}}
div[class*="st-key-card-dark-"] .progress-track {{ background: rgba(255,255,255,0.18); }}
.progress-fill {{
  height: 100%;
  border-radius: 999px;
}}

/* --- Callout / nota (limitaciones, accesibilidad) ------------------------ */
.callout {{
  font-family: {FONT_SANS};
  font-size: 0.82rem;
  color: {TEXT_MUTED};
  background: rgba(46, 134, 171, 0.07);
  border-left: 3px solid {TEAL};
  border-radius: 0.5rem;
  padding: 0.6rem 0.85rem;
  margin-top: 0.6rem;
}}
.callout b {{ color: {NAVY}; }}

/* --- Titulo de seccion (dentro de una card) ------------------------------ */
.section-title {{
  font-family: {FONT_SERIF};
  font-size: 1.15rem;
  font-weight: 700;
  color: {NAVY};
  margin-bottom: 0.15rem;
}}
div[class*="st-key-card-dark-"] .section-title {{ color: white; }}
.section-caption {{
  font-family: {FONT_SANS};
  font-size: 0.85rem;
  color: {TEXT_MUTED};
  margin-bottom: 0.6rem;
}}
</style>
"""


def inject_global_css():
    st.markdown(_css(), unsafe_allow_html=True)


@contextmanager
def card(name: str, variant: str = "light"):
    """Card reutilizable. variant: 'light' | 'dark' | 'mvp'.

    El radio de esquina y el borde los resuelve el theme de Streamlit
    (.streamlit/config.toml: baseRadius); esta funcion solo aporta fondo,
    sombra y color de texto via la clase st-key-card-{variant}-{name}.
    """
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


def progress_pill(pct: float, color: str = RED):
    pct = max(0.0, min(100.0, pct))
    st.markdown(
        f'<div class="progress-track"><div class="progress-fill" '
        f'style="width:{pct:.0f}%; background:{color};"></div></div>',
        unsafe_allow_html=True,
    )
