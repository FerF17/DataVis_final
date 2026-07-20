"""
app.py
Dashboard "Anatomia del riesgo de mercado -- Calma vs Crisis".

Fases A/B/C completas:
  - Vista 1  Overview temporal          (Fase B)
  - Vista 2  Volatilidad por regimen    (Fase B)
  - Vista 3  Correlacion por regimen    (Fase B, MVP) + correlacion rolling de un par (Fase C)
  - Vista 4  Drawdown (underwater)       (Fase C)
  - Vista 5  Distribucion de retornos    (Fase C)
  - Vista 6  Red de contagio             (Fase C, opcional / stretch)

Interacciones (Fase C):
  - Filtro global de regimen + selector de episodio (COVID-2020, tasas-2022) o rango manual.
  - Seleccion de activos (multiselect) que aplica a las 6 vistas.
  - Resaltado enlazado: un activo "en foco" (sidebar, via st.session_state) se resalta
    de forma coherente en TODAS las vistas -- vistas coordinadas (CMV).
  - Selector de par + correlacion rolling del par elegido.
  - Tooltips enriquecidos y hover unificado en las series temporales.

Datos: importa cargar_datos()/build_dataset() de pipeline.py. En local usa el parquet
cacheado; en la nube (sin parquet) lo regenera desde Yahoo Finance en el primer arranque.
Ejecutar: streamlit run app.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import styles
from pipeline import MIN_OBS_CORR

ETIQUETAS_ACTIVO = {
    "SPY": "SPY (Acciones)", "QQQ": "QQQ (Tech)", "TLT": "TLT (Bonos LP)",
    "GLD": "GLD (Oro)", "HYG": "HYG (HY Credito)", "VNQ": "VNQ (Real Estate)",
    "EEM": "EEM (Emergentes)", "DBC": "DBC (Commodities)", "UUP": "UUP (Dolar)",
    "BTC-USD": "BTC-USD (Cripto)",
}

NAV_OPTIONS = ["Overview", "Volatilidad", "Correlacion", "Drawdown", "Distribucion", "Contagio"]

SIN_FOCO = "(ninguno)"


# ============================================================================
# Carga de datos (cacheada). Bootstrap: si no hay parquet (deploy limpio en la
# nube), se regenera el dataset desde Yahoo Finance una sola vez por arranque.
# ============================================================================
@st.cache_data(show_spinner="Cargando datos de mercado...")
def cargar():
    from pipeline import cargar_datos, build_dataset
    try:
        return cargar_datos()
    except FileNotFoundError:
        # Primer arranque en un entorno sin salidas/ (p. ej. Streamlit Cloud).
        return build_dataset()


# ---------------------------------------------------------------------------
# Helpers de resaltado enlazado
# ---------------------------------------------------------------------------
def _opacidad(activo, foco):
    """Opacidad de una traza segun el activo en foco (resaltado enlazado)."""
    if foco == SIN_FOCO:
        return 1.0
    return 1.0 if activo == foco else 0.18


def _ancho(activo, foco, base=1.6):
    if foco == SIN_FOCO:
        return base
    return base + 1.8 if activo == foco else base * 0.7


# ============================================================================
# Vista 1 - Overview temporal
# ============================================================================
def render_overview(precios, vix, crisis_din, activos_sel, umbral_vix, rango_fechas, foco):
    vix_actual = vix.iloc[-1] if len(vix) else float("nan")
    regimen_actual = "Crisis" if vix_actual > umbral_vix else "Calma"
    pct_crisis = 100 * crisis_din.reindex(precios.index).fillna(False).mean()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        with styles.card("vix", variant="dark"):
            styles.icon_corner("\U0001F321")
            styles.hero_metric(f"{vix_actual:.1f}", "VIX ACTUAL")
            st.markdown(
                styles.badge(regimen_actual, variant="teal" if regimen_actual == "Calma" else "red"),
                unsafe_allow_html=True,
            )
    with col2:
        with styles.card("umbral"):
            styles.hero_metric(f"{umbral_vix}", "UMBRAL CRISIS", sub="VIX > umbral")
    with col3:
        with styles.card("pct-crisis"):
            styles.hero_metric(f"{pct_crisis:.1f}%", "DIAS EN CRISIS (rango)")
            styles.progress_pill(pct_crisis, color=styles.RED)
    with col4:
        with styles.card("activos"):
            styles.hero_metric(f"{len(activos_sel)}", "ACTIVOS EN VISTA",
                                sub=f"{rango_fechas[0]} → {rango_fechas[1]}")

    with styles.card("overview-chart"):
        styles.icon_corner("↗")
        styles.section_title(
            "Overview temporal",
            "Precios normalizados (base 100) por activo, sombreado de crisis y VIX con umbral.",
        )

        precios_norm = precios / precios.bfill().iloc[0] * 100
        fig1 = make_subplots(
            rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.06,
        )

        crisis_bool = crisis_din.reindex(precios.index).fillna(False)
        if crisis_bool.any():
            bloques = (crisis_bool != crisis_bool.shift()).cumsum()
            for _, grupo in crisis_bool[crisis_bool].groupby(bloques[crisis_bool]):
                x0, x1 = grupo.index.min(), grupo.index.max()
                fig1.add_vrect(x0=x0, x1=x1, fillcolor=styles.RED, opacity=0.10, line_width=0, row=1, col=1)
                fig1.add_vrect(x0=x0, x1=x1, fillcolor=styles.RED, opacity=0.10, line_width=0, row=2, col=1)

        for activo in activos_sel:
            color = styles.color_activo(activo)
            fig1.add_trace(
                go.Scatter(
                    x=precios_norm.index, y=precios_norm[activo], mode="lines",
                    name=ETIQUETAS_ACTIVO.get(activo, activo),
                    line=dict(color=color, width=_ancho(activo, foco)),
                    opacity=_opacidad(activo, foco),
                    hovertemplate=f"{ETIQUETAS_ACTIVO.get(activo, activo)}<br>%{{x|%Y-%m-%d}}: %{{y:.1f}}<extra></extra>",
                ),
                row=1, col=1,
            )

        fig1.add_trace(
            go.Scatter(
                x=vix.index, y=vix, mode="lines", name="VIX", line=dict(color=styles.NAVY, width=1.4),
                hovertemplate="VIX<br>%{x|%Y-%m-%d}: %{y:.1f}<extra></extra>", showlegend=False,
            ),
            row=2, col=1,
        )
        fig1.add_hline(
            y=umbral_vix, line_dash="dash", line_color=styles.RED, row=2, col=1,
            annotation_text=f"umbral {umbral_vix}", annotation_position="top left",
            annotation_font_color=styles.RED,
        )

        fig1.update_yaxes(title_text="Precio (base 100)", gridcolor=styles.GRID, row=1, col=1)
        fig1.update_yaxes(title_text="VIX", gridcolor=styles.GRID, row=2, col=1)
        fig1.update_xaxes(gridcolor=styles.GRID, row=2, col=1)
        fig1.update_layout(
            height=520,
            **styles.PLOTLY_TRANSPARENT,
            font=dict(family=styles.FONT_SANS, color=styles.NAVY),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=30, b=10, l=10, r=10),
        )
        st.plotly_chart(fig1, width="stretch")


# ============================================================================
# Vista 2 - Volatilidad por regimen
# ============================================================================
def render_volatilidad(vol, regimen_din, regimen_filtro, activos_sel, foco):
    with styles.card("volatilidad"):
        styles.section_title(
            "Volatilidad por regimen",
            "Volatilidad realizada anualizada (rolling 21d, √252) promedio por activo, Calma vs Crisis.",
        )

        vol_calma = vol[regimen_din.reindex(vol.index) == "Calma"].mean() * 100
        vol_crisis = vol[regimen_din.reindex(vol.index) == "Crisis"].mean() * 100

        etiquetas_x = [ETIQUETAS_ACTIVO.get(a, a) for a in activos_sel]
        # Resaltado enlazado: la barra del activo en foco se opaca menos que el resto.
        op = [1.0 if (foco == SIN_FOCO or a == foco) else 0.28 for a in activos_sel]

        fig2 = go.Figure()
        if regimen_filtro in ("Ambos", "Calma"):
            fig2.add_trace(go.Bar(
                x=etiquetas_x, y=vol_calma.values, name="Calma", marker_color=styles.TEAL,
                marker_opacity=op,
                text=[f"{v:.0f}" if pd.notna(v) else "" for v in vol_calma.values], textposition="outside",
                hovertemplate="%{x}<br>Calma: %{y:.1f}%<extra></extra>",
            ))
        if regimen_filtro in ("Ambos", "Crisis"):
            fig2.add_trace(go.Bar(
                x=etiquetas_x, y=vol_crisis.values, name="Crisis", marker_color=styles.RED,
                marker_opacity=op,
                text=[f"{v:.0f}" if pd.notna(v) else "" for v in vol_crisis.values], textposition="outside",
                hovertemplate="%{x}<br>Crisis: %{y:.1f}%<extra></extra>",
            ))

        titulo_vol = "La volatilidad se multiplica en crisis"
        mult = (vol_crisis / vol_calma).replace([np.inf, -np.inf], np.nan).dropna()
        if len(mult) > 0:
            top = mult.sort_values(ascending=False).head(2)
            detalle = ", ".join(f"{a} ×{v:.1f}" for a, v in top.items())
            titulo_vol += f"  —  {detalle}"

        fig2.update_layout(
            title=dict(text=titulo_vol, font=dict(family=styles.FONT_SERIF, size=17, color=styles.NAVY)),
            barmode="group",
            **styles.PLOTLY_TRANSPARENT,
            font=dict(family=styles.FONT_SANS, color=styles.NAVY),
            yaxis=dict(title="Volatilidad anualizada (%)", gridcolor=styles.GRID),
            xaxis=dict(gridcolor=styles.GRID),
            legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="right", x=1),
            height=460,
            margin=dict(t=70, b=10, l=10, r=10),
        )
        st.plotly_chart(fig2, width="stretch")


# ============================================================================
# Vista 3 - Matriz de correlacion por regimen (MVP) + correlacion rolling de un par
# ============================================================================
def render_correlacion(retornos, regimen_din, regimen_filtro, activos_sel, min_obs_corr,
                       crisis_din, umbral_vix, foco):
    with styles.card("correlacion", variant="mvp"):
        styles.section_title(
            "Matriz de correlacion por regimen",
            "Colormap divergente (RdBu) centrado en 0, segura para daltonicos. El bloque de riesgo "
            "converge hacia 1 en crisis; el refugio real (bonos largos) se desacopla mas.",
            badge_html=styles.badge("MVP · PRIORIDAD #1", variant="red"),
        )

        if len(activos_sel) < 2:
            st.info("Seleccione al menos 2 activos para calcular la matriz de correlacion.")
            return

        etiquetas_x = [ETIQUETAS_ACTIVO.get(a, a) for a in activos_sel]
        regimen_ret = regimen_din.reindex(retornos.index)
        corr_calma = retornos[regimen_ret == "Calma"].corr(min_periods=min_obs_corr)
        corr_crisis = retornos[regimen_ret == "Crisis"].corr(min_periods=min_obs_corr)

        n_calma = int((regimen_ret == "Calma").sum())
        n_crisis = int((regimen_ret == "Crisis").sum())
        if n_crisis < min_obs_corr:
            st.warning(
                f"Solo hay {n_crisis} dias de Crisis en el rango/umbral seleccionado "
                f"(minimo recomendado: {min_obs_corr}). La matriz de Crisis puede ser poco confiable o mostrar NaN."
            )

        paneles = []
        if regimen_filtro in ("Ambos", "Calma"):
            paneles.append(("CALMA", corr_calma, n_calma))
        if regimen_filtro in ("Ambos", "Crisis"):
            paneles.append(("CRISIS", corr_crisis, n_crisis))

        fig3 = make_subplots(
            rows=1, cols=len(paneles), horizontal_spacing=0.12,
            subplot_titles=[f"{nombre}  (n={n} dias)" for nombre, _, n in paneles],
        )
        for col_idx, (_, corr, _) in enumerate(paneles, start=1):
            fig3.add_trace(
                go.Heatmap(
                    z=corr.values, x=etiquetas_x, y=etiquetas_x, coloraxis="coloraxis",
                    texttemplate="%{z:.2f}", textfont=dict(size=11),
                    hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
                ),
                row=1, col=col_idx,
            )
            fig3.update_yaxes(autorange="reversed", row=1, col=col_idx)
            # Resaltado enlazado: recuadro sobre la fila/columna del activo en foco.
            if foco != SIN_FOCO and foco in activos_sel:
                j = activos_sel.index(foco)
                fig3.add_shape(
                    type="rect", xref=f"x{col_idx if col_idx > 1 else ''}",
                    yref=f"y{col_idx if col_idx > 1 else ''}",
                    x0=-0.5, x1=len(activos_sel) - 0.5, y0=j - 0.5, y1=j + 0.5,
                    line=dict(color=styles.NAVY, width=2.5), fillcolor="rgba(0,0,0,0)",
                    row=1, col=col_idx,
                )
                fig3.add_shape(
                    type="rect", x0=j - 0.5, x1=j + 0.5, y0=-0.5, y1=len(activos_sel) - 0.5,
                    line=dict(color=styles.NAVY, width=2.5), fillcolor="rgba(0,0,0,0)",
                    row=1, col=col_idx,
                )

        fig3.update_layout(
            coloraxis=dict(colorscale="RdBu_r", cmin=-1, cmax=1,
                            colorbar=dict(title="Correlacion", thickness=14)),
            **styles.PLOTLY_TRANSPARENT,
            font=dict(family=styles.FONT_SANS, color=styles.NAVY),
            height=520,
            margin=dict(t=50, b=10, l=10, r=10),
        )
        fig3.update_annotations(font=dict(family=styles.FONT_SERIF, size=14, color=styles.NAVY))
        st.plotly_chart(fig3, width="stretch")

    # --- Correlacion rolling de un par elegido (interaccion Fase C, paso 14) ---
    with styles.card("corr-par"):
        styles.icon_corner("∿")
        styles.section_title(
            "Correlacion rolling de un par",
            "Correlacion movil (ventana 63d ≈ 1 trimestre) del par elegido, con sombreado de crisis. "
            "Muestra COMO evoluciona el acoplamiento en el tiempo, no solo su promedio por regimen.",
        )
        c1, c2, c3 = st.columns([3, 3, 2])
        idx_def_a = activos_sel.index(foco) if foco in activos_sel else 0
        with c1:
            par_a = st.selectbox("Activo A", activos_sel, index=idx_def_a,
                                 format_func=lambda a: ETIQUETAS_ACTIVO.get(a, a), key="par_a")
        opciones_b = [a for a in activos_sel if a != par_a] or activos_sel
        with c2:
            par_b = st.selectbox("Activo B", opciones_b,
                                 format_func=lambda a: ETIQUETAS_ACTIVO.get(a, a), key="par_b")
        with c3:
            ventana = st.select_slider("Ventana (dias)", options=[21, 42, 63, 126, 252], value=63,
                                       key="corr_win")

        roll = retornos[par_a].rolling(ventana, min_periods=int(ventana * 0.6)).corr(retornos[par_b])
        media_calma = roll[regimen_din.reindex(roll.index) == "Calma"].mean()
        media_crisis = roll[regimen_din.reindex(roll.index) == "Crisis"].mean()

        figp = go.Figure()
        crisis_bool = crisis_din.reindex(roll.index).fillna(False)
        if crisis_bool.any():
            bloques = (crisis_bool != crisis_bool.shift()).cumsum()
            for _, grupo in crisis_bool[crisis_bool].groupby(bloques[crisis_bool]):
                figp.add_vrect(x0=grupo.index.min(), x1=grupo.index.max(),
                               fillcolor=styles.RED, opacity=0.10, line_width=0)
        figp.add_trace(go.Scatter(
            x=roll.index, y=roll, mode="lines", line=dict(color=styles.TEAL, width=1.8),
            name=f"{par_a}–{par_b}",
            hovertemplate=f"{par_a}–{par_b}<br>%{{x|%Y-%m-%d}}: %{{y:.2f}}<extra></extra>",
        ))
        for y, txt, col in [(media_calma, "media calma", styles.NAVY), (media_crisis, "media crisis", styles.RED)]:
            if pd.notna(y):
                figp.add_hline(y=y, line_dash="dot", line_color=col,
                               annotation_text=f"{txt}: {y:.2f}", annotation_font_color=col,
                               annotation_position="top left")
        figp.update_layout(
            **styles.PLOTLY_TRANSPARENT,
            font=dict(family=styles.FONT_SANS, color=styles.NAVY),
            yaxis=dict(title="Correlacion rolling", gridcolor=styles.GRID, range=[-1, 1]),
            xaxis=dict(gridcolor=styles.GRID),
            height=340, margin=dict(t=20, b=10, l=10, r=10), showlegend=False,
        )
        st.plotly_chart(figp, width="stretch")


# ============================================================================
# Vista 4 - Drawdown (underwater) + ranking de peor caida y recuperacion
# ============================================================================
def _stats_drawdown(dd):
    """Peor drawdown, fecha del valle y dias hasta recuperar el maximo previo, por activo."""
    filas = []
    for a in dd.columns:
        s = dd[a].dropna()
        if s.empty:
            continue
        valle = s.idxmin()
        peor = s.min()
        post = s.loc[valle:]
        recuperado = post[post >= -1e-6]
        if len(recuperado):
            dias_rec = (recuperado.index[0] - valle).days
            rec_txt = f"{dias_rec} d"
        else:
            rec_txt = "sin recuperar"
        filas.append({
            "Activo": ETIQUETAS_ACTIVO.get(a, a),
            "_codigo": a,
            "Peor drawdown": peor * 100,
            "Fecha valle": valle.date().isoformat(),
            "Recuperacion": rec_txt,
        })
    return pd.DataFrame(filas).sort_values("Peor drawdown")


def render_drawdown(drawdown, crisis_din, activos_sel, regimen_filtro, foco):
    dd = drawdown[activos_sel]
    stats = _stats_drawdown(dd)

    # Hero row
    col1, col2, col3 = st.columns(3)
    if not stats.empty:
        peor_fila = stats.iloc[0]
        sin_rec = stats[stats["Recuperacion"] == "sin recuperar"]
        with col1:
            with styles.card("dd-peor", variant="dark"):
                styles.icon_corner("↓")
                styles.hero_metric(f"{peor_fila['Peor drawdown']:.1f}%", "PEOR DRAWDOWN",
                                    sub=f"{peor_fila['Activo']} · {peor_fila['Fecha valle']}")
        with col2:
            with styles.card("dd-prom"):
                styles.hero_metric(f"{stats['Peor drawdown'].mean():.1f}%", "PEOR DD PROMEDIO",
                                    sub=f"{len(stats)} activos en vista")
        with col3:
            with styles.card("dd-sinrec"):
                styles.hero_metric(f"{len(sin_rec)}", "SIN RECUPERAR",
                                    sub="no vuelven a su maximo previo")

    with styles.card("drawdown-chart"):
        styles.icon_corner("~")
        styles.section_title(
            "Drawdown (underwater plot)",
            "Caida desde el maximo historico previo, por activo. Las bandas rojas marcan crisis. "
            "La diversificacion falla justo cuando todo cae a la vez.",
        )
        fig4 = go.Figure()
        crisis_bool = crisis_din.reindex(dd.index).fillna(False)
        if crisis_bool.any():
            bloques = (crisis_bool != crisis_bool.shift()).cumsum()
            for _, grupo in crisis_bool[crisis_bool].groupby(bloques[crisis_bool]):
                fig4.add_vrect(x0=grupo.index.min(), x1=grupo.index.max(),
                               fillcolor=styles.RED, opacity=0.08, line_width=0)
        for a in activos_sel:
            fig4.add_trace(go.Scatter(
                x=dd.index, y=dd[a] * 100, mode="lines", name=ETIQUETAS_ACTIVO.get(a, a),
                line=dict(color=styles.color_activo(a), width=_ancho(a, foco, base=1.3)),
                opacity=_opacidad(a, foco),
                hovertemplate=f"{ETIQUETAS_ACTIVO.get(a, a)}<br>%{{x|%Y-%m-%d}}: %{{y:.1f}}%<extra></extra>",
            ))
        fig4.update_layout(
            **styles.PLOTLY_TRANSPARENT,
            font=dict(family=styles.FONT_SANS, color=styles.NAVY),
            hovermode="x unified",
            yaxis=dict(title="Drawdown (%)", gridcolor=styles.GRID, rangemode="tozero"),
            xaxis=dict(gridcolor=styles.GRID),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            height=460, margin=dict(t=30, b=10, l=10, r=10),
        )
        st.plotly_chart(fig4, width="stretch")

    with styles.card("drawdown-rank"):
        styles.section_title(
            "Ranking de peor drawdown y recuperacion",
            "Ordenado de la peor caida a la menos mala. 'Recuperacion' = dias desde el valle hasta "
            "volver al maximo previo.",
        )
        if not stats.empty:
            cols = ["Activo", "Peor drawdown", "Fecha valle", "Recuperacion"]
            tabla = stats[cols].copy()
            tabla["Peor drawdown"] = tabla["Peor drawdown"].map(lambda v: f"{v:.1f}%")
            st.dataframe(tabla, width="stretch", hide_index=True)


# ============================================================================
# Vista 5 - Distribucion de retornos (colas gordas por regimen)
# ============================================================================
def render_distribucion(retornos, regimen_din, regimen_filtro, activos_sel, foco):
    with styles.card("distribucion"):
        styles.icon_corner("◔")
        styles.section_title(
            "Distribucion de retornos por regimen",
            "Violines de retornos diarios (%) por activo, Calma vs Crisis. En crisis la distribucion "
            "se ensancha y las colas engordan: los dias extremos dejan de ser raros (riesgo de cola).",
        )

        regimen_ret = regimen_din.reindex(retornos.index)
        etiquetas_x = [ETIQUETAS_ACTIVO.get(a, a) for a in activos_sel]

        fig5 = go.Figure()
        datos_largos = []
        for a in activos_sel:
            for reg, color in [("Calma", styles.TEAL), ("Crisis", styles.RED)]:
                if regimen_filtro not in ("Ambos", reg):
                    continue
                serie = (retornos[a][regimen_ret == reg] * 100).dropna()
                if serie.empty:
                    continue
                datos_largos.append((a, reg, serie))

        for a, reg, serie in datos_largos:
            color = styles.TEAL if reg == "Calma" else styles.RED
            op = 1.0 if (foco == SIN_FOCO or a == foco) else 0.28
            fig5.add_trace(go.Violin(
                x=[ETIQUETAS_ACTIVO.get(a, a)] * len(serie), y=serie.values,
                name=reg, legendgroup=reg, scalegroup=reg, showlegend=False,
                side="negative" if reg == "Calma" else "positive",
                line_color=color, fillcolor=color, opacity=op, points=False,
                meanline_visible=True, width=0.9,
                hovertemplate=f"{ETIQUETAS_ACTIVO.get(a, a)} · {reg}<br>%{{y:.2f}}%<extra></extra>",
            ))
        # Trazas fantasma solo para la leyenda Calma/Crisis
        for reg, color in [("Calma", styles.TEAL), ("Crisis", styles.RED)]:
            if regimen_filtro in ("Ambos", reg):
                fig5.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                                          marker=dict(color=color, size=10), name=reg))

        fig5.update_layout(
            violinmode="overlay",
            **styles.PLOTLY_TRANSPARENT,
            font=dict(family=styles.FONT_SANS, color=styles.NAVY),
            yaxis=dict(title="Retorno diario (%)", gridcolor=styles.GRID, zeroline=True,
                       zerolinecolor=styles.GRID),
            xaxis=dict(gridcolor=styles.GRID),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=480, margin=dict(t=30, b=10, l=10, r=10),
        )
        st.plotly_chart(fig5, width="stretch")

    with styles.card("dist-colas"):
        styles.section_title(
            "Cuantificacion de las colas (curtosis y peor dia)",
            "Curtosis en exceso > 0 = colas mas gordas que una normal. El peor dia por regimen "
            "muestra cuanto peor puede ser un solo dia en crisis.",
        )
        filas = []
        regimen_ret = regimen_din.reindex(retornos.index)
        for a in activos_sel:
            fila = {"Activo": ETIQUETAS_ACTIVO.get(a, a)}
            for reg in ("Calma", "Crisis"):
                serie = retornos[a][regimen_ret == reg].dropna()
                if len(serie) > 3:
                    fila[f"Curtosis {reg}"] = f"{serie.kurtosis():.1f}"
                    fila[f"Peor dia {reg}"] = f"{serie.min() * 100:.1f}%"
                else:
                    fila[f"Curtosis {reg}"] = "—"
                    fila[f"Peor dia {reg}"] = "—"
            filas.append(fila)
        st.dataframe(pd.DataFrame(filas), width="stretch", hide_index=True)


# ============================================================================
# Vista 6 - Red de contagio (opcional / stretch)
# ============================================================================
def render_contagio(retornos, regimen_din, activos_sel, foco):
    with styles.card("contagio"):
        styles.icon_corner("◈")
        styles.section_title(
            "Red de contagio",
            "Grafo de correlaciones: cada nodo es un activo y cada arista un par cuya correlacion "
            "supera el umbral. Al pasar de Calma a Crisis aparecen mas aristas y mas gruesas: el "
            "mercado se vuelve un solo bloque.",
            badge_html=styles.badge("OPCIONAL · STRETCH", variant="amber"),
        )

        if len(activos_sel) < 2:
            st.info("Seleccione al menos 2 activos para dibujar la red de contagio.")
            return

        c1, c2 = st.columns([2, 3])
        with c1:
            umbral_arista = st.slider("Umbral de correlacion |ρ|", 0.0, 1.0, 0.5, 0.05,
                                      key="contagio_umbral")
        with c2:
            regimen_red = st.radio("Regimen a dibujar", ["Calma", "Crisis"], horizontal=True,
                                   index=1, key="contagio_regimen")

        regimen_ret = regimen_din.reindex(retornos.index)
        corr = retornos[activos_sel][regimen_ret == regimen_red].corr(min_periods=MIN_OBS_CORR)

        n = len(activos_sel)
        angulos = np.linspace(0, 2 * np.pi, n, endpoint=False)
        pos = {a: (np.cos(t), np.sin(t)) for a, t in zip(activos_sel, angulos)}

        fig6 = go.Figure()
        n_aristas = 0
        for i in range(n):
            for j in range(i + 1, n):
                a, b = activos_sel[i], activos_sel[j]
                r = corr.iloc[i, j]
                if pd.isna(r) or abs(r) < umbral_arista:
                    continue
                n_aristas += 1
                x0, y0 = pos[a]
                x1, y1 = pos[b]
                col = styles.RED if r > 0 else styles.TEAL
                resaltar = foco == SIN_FOCO or foco in (a, b)
                fig6.add_trace(go.Scatter(
                    x=[x0, x1], y=[y0, y1], mode="lines",
                    line=dict(color=col, width=1 + 5 * abs(r)),
                    opacity=(0.75 if resaltar else 0.10),
                    hoverinfo="text", text=f"{a}–{b}: {r:.2f}", showlegend=False,
                ))

        for a in activos_sel:
            x, y = pos[a]
            foco_nodo = foco == SIN_FOCO or a == foco
            fig6.add_trace(go.Scatter(
                x=[x], y=[y], mode="markers+text", text=[a], textposition="middle center",
                textfont=dict(color="white", size=9, family=styles.FONT_SANS),
                marker=dict(size=42, color=styles.color_activo(a),
                            line=dict(color=styles.NAVY if a == foco and foco != SIN_FOCO else "white",
                                      width=3 if a == foco and foco != SIN_FOCO else 1.5)),
                opacity=(1.0 if foco_nodo else 0.3),
                hovertemplate=f"{ETIQUETAS_ACTIVO.get(a, a)}<extra></extra>", showlegend=False,
            ))

        fig6.update_layout(
            **styles.PLOTLY_TRANSPARENT,
            font=dict(family=styles.FONT_SANS, color=styles.NAVY),
            xaxis=dict(visible=False, range=[-1.4, 1.4]),
            yaxis=dict(visible=False, range=[-1.4, 1.4], scaleanchor="x", scaleratio=1),
            height=560, margin=dict(t=10, b=10, l=10, r=10),
        )
        st.plotly_chart(fig6, width="stretch")
        styles.note(
            f"<b>{n_aristas}</b> aristas sobre el umbral |ρ|≥{umbral_arista:.2f} en regimen "
            f"<b>{regimen_red}</b>. Rojo = correlacion positiva (se mueven juntos), "
            f"teal = negativa (cobertura). Sube el umbral o cambia de regimen para ver el contagio."
        )


# ============================================================================
# Main
# ============================================================================
st.set_page_config(
    page_title="Anatomia del riesgo de mercado",
    page_icon="\U0001F4C9",
    layout="wide",
)
styles.inject_global_css()

data = cargar()
precios_todo = data["precios"]
vix_todo = data["vix"]
retornos_todo = data["retornos"]
vol_todo = data["vol_realizada"]
drawdown_todo = data["drawdown"]
umbral_defecto = int(data["umbral_crisis"])

# --- Sidebar: panel de control ----------------------------------------------
st.sidebar.markdown("## Panel de control")

activos_sel = st.sidebar.multiselect(
    "Activos",
    options=list(precios_todo.columns),
    default=list(precios_todo.columns),
    format_func=lambda a: ETIQUETAS_ACTIVO.get(a, a),
)

# Resaltado enlazado (CMV): el activo en foco se resalta en las 6 vistas.
foco = st.sidebar.selectbox(
    "Resaltar activo (enlazado)",
    options=[SIN_FOCO] + list(precios_todo.columns),
    format_func=lambda a: a if a == SIN_FOCO else ETIQUETAS_ACTIVO.get(a, a),
    key="activo_focus",
    help="Resalta el mismo activo de forma coherente en todas las vistas (vistas coordinadas).",
)

fecha_min = precios_todo.index.min().date()
fecha_max = precios_todo.index.max().date()

# Selector de episodio (brush rapido) o rango manual.
EPISODIOS = {
    "Todo el periodo": (fecha_min, fecha_max),
    "COVID-19 (2020)": (pd.Timestamp("2020-01-01").date(), pd.Timestamp("2020-12-31").date()),
    "Alza de tasas (2022)": (pd.Timestamp("2022-01-01").date(), pd.Timestamp("2022-12-31").date()),
    "Personalizado": None,
}
episodio = st.sidebar.selectbox("Episodio", list(EPISODIOS.keys()), index=0)
if episodio == "Personalizado":
    rango_fechas = st.sidebar.slider(
        "Rango de fechas", min_value=fecha_min, max_value=fecha_max,
        value=(fecha_min, fecha_max), format="YYYY-MM-DD",
    )
else:
    rango_fechas = EPISODIOS[episodio]
    # Recorta el preset al rango realmente disponible en los datos.
    rango_fechas = (max(rango_fechas[0], fecha_min), min(rango_fechas[1], fecha_max))

umbral_vix = st.sidebar.number_input(
    "Umbral crisis VIX", min_value=10, max_value=60, value=umbral_defecto, step=1,
    help="VIX > umbral se clasifica como Crisis. Por defecto 30 (regla ya validada).",
)

regimen_filtro = st.sidebar.radio("Regimen", ["Ambos", "Calma", "Crisis"], horizontal=True)

st.sidebar.caption("Fuente: Yahoo Finance (yfinance) · 2018–2026 · datos 100% reales")

if len(activos_sel) == 0:
    st.warning("Seleccione al menos un activo en el panel de control para ver el dashboard.")
    st.stop()

# --- Filtrado comun ----------------------------------------------------------
mask_fecha = (precios_todo.index.date >= rango_fechas[0]) & (precios_todo.index.date <= rango_fechas[1])

precios = precios_todo.loc[mask_fecha, activos_sel]
vix = vix_todo.loc[mask_fecha]
retornos = retornos_todo.loc[mask_fecha, activos_sel]
vol = vol_todo.loc[mask_fecha, activos_sel]
drawdown = drawdown_todo.loc[mask_fecha, activos_sel]

crisis_din = vix > umbral_vix
regimen_din = pd.Series(np.where(crisis_din, "Crisis", "Calma"), index=vix.index, name="regimen")

# --- Topbar: titulo + nav + subtitulo ----------------------------------------
with st.container(key="topbar", horizontal=True, vertical_alignment="center"):
    st.markdown(
        '<div class="topbar-title">Anatomia del riesgo &middot; Calma vs Crisis</div>',
        unsafe_allow_html=True,
    )
    seleccion = st.segmented_control(
        "Navegacion", NAV_OPTIONS, default=NAV_OPTIONS[0], key="nav_tab",
        label_visibility="collapsed",
    )
    st.markdown('<div class="topbar-sub">Streamlit + Plotly</div>', unsafe_allow_html=True)

if seleccion is None:
    seleccion = NAV_OPTIONS[0]

if seleccion == "Overview":
    render_overview(precios, vix, crisis_din, activos_sel, umbral_vix, rango_fechas, foco)
elif seleccion == "Volatilidad":
    render_volatilidad(vol, regimen_din, regimen_filtro, activos_sel, foco)
elif seleccion == "Correlacion":
    render_correlacion(retornos, regimen_din, regimen_filtro, activos_sel, MIN_OBS_CORR,
                       crisis_din, umbral_vix, foco)
elif seleccion == "Drawdown":
    render_drawdown(drawdown, crisis_din, activos_sel, regimen_filtro, foco)
elif seleccion == "Distribucion":
    render_distribucion(retornos, regimen_din, regimen_filtro, activos_sel, foco)
elif seleccion == "Contagio":
    render_contagio(retornos, regimen_din, activos_sel, foco)

st.caption(
    "Fases A-C completas · 6 vistas coordinadas · datos reales de Yahoo Finance (2018–2026). "
    "Limitaciones de datos documentadas en el README y en la nota de cada vista."
)
