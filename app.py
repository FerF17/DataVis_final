"""
app.py
Dashboard "Anatomia del riesgo de mercado -- Calma vs Crisis".

Vistas:
  - Vista 1  Overview temporal
  - Vista 2  Volatilidad por regimen
  - Vista 3  Correlacion por regimen (MVP) + correlacion rolling de un par
  - Vista 4  Drawdown (underwater)
  - Vista 5  Distribucion de retornos
  - Vista 6  Red de contagio (opcional / stretch)

Interacciones:
  - Filtro global de regimen + selector de episodio (COVID-2020, tasas-2022) o rango manual.
  - Seleccion de activos (multiselect) que aplica a las 6 vistas.
  - Resaltado enlazado: un activo "en foco" (sidebar, via st.session_state) se resalta
    de forma coherente en TODAS las vistas -- vistas coordinadas (CMV).
  - Selector de par + correlacion rolling del par elegido.
  - Tooltips enriquecidos y hover unificado en las series temporales.

Capas transversales:
  - `narrativa.py`  -- lectura guiada parametrizada: cada pantalla se explica sola
    para la combinacion de ETFs, rango, umbral y regimen que tenga el usuario.
  - `reporte.py`    -- self-report en PDF con las seis pantallas, disponible al pie
    de cada vista.

Datos: importa cargar_datos()/build_dataset() de pipeline.py.
Ejecutar: streamlit run app.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import narrativa
import reporte
import styles
from narrativa import ETIQUETAS_ACTIVO, SIN_FOCO
from pipeline import MIN_OBS_CORR

NAV_OPTIONS = ["Overview", "Volatilidad", "Correlacion", "Drawdown", "Distribucion", "Contagio"]


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
    return 1.0 if activo == foco else 0.16


def _ancho(activo, foco, base=1.9):
    if foco == SIN_FOCO:
        return base
    return base + 1.4 if activo == foco else base * 0.65


def _bandas_crisis(fig, crisis_bool, **kwargs):
    """Sombreado calido de los tramos continuos de crisis."""
    crisis_bool = crisis_bool.fillna(False)
    if not crisis_bool.any():
        return
    bloques = (crisis_bool != crisis_bool.shift()).cumsum()
    for _, grupo in crisis_bool[crisis_bool].groupby(bloques[crisis_bool]):
        fig.add_vrect(x0=grupo.index.min(), x1=grupo.index.max(),
                      fillcolor=styles.CRISIS, opacity=0.09, line_width=0, layer="below",
                      **kwargs)


# ============================================================================
# Vista 1 - Overview temporal
# ============================================================================
def render_overview(precios, vix, crisis_din, activos_sel, umbral_vix, rango_fechas,
                    regimen_filtro, foco):
    vix_actual = vix.iloc[-1] if len(vix) else float("nan")
    regimen_actual = "Crisis" if vix_actual > umbral_vix else "Calma"
    pct_crisis = 100 * crisis_din.reindex(precios.index).fillna(False).mean()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        with styles.card("vix", variant="dark"):
            styles.icon_corner("\U0001F321")
            styles.hero_metric(f"{vix_actual:.1f}", "VIX AL CIERRE DEL RANGO")
            st.markdown(
                styles.badge(regimen_actual, variant="mist"),
                unsafe_allow_html=True,
            )
    with col2:
        with styles.card("umbral"):
            styles.hero_metric(f"{umbral_vix}", "UMBRAL DE CRISIS", sub="Se marca crisis si VIX supera este valor")
    with col3:
        with styles.card("pct-crisis"):
            styles.hero_metric(f"{pct_crisis:.1f}%", "DIAS EN CRISIS (RANGO)")
            styles.progress_pill(pct_crisis, color=styles.CRISIS)
    with col4:
        with styles.card("activos"):
            styles.hero_metric(f"{len(activos_sel)}", "ACTIVOS EN VISTA",
                               sub=f"{rango_fechas[0]} → {rango_fechas[1]}")

    with styles.card("overview-chart"):
        styles.icon_corner("↗")
        styles.section_title(
            "Overview temporal",
            "Precios normalizados a base 100, sombreado de los episodios de crisis y el VIX "
            "que los origina, en el mismo eje de tiempo.",
        )

        bloque = narrativa.overview(precios, vix, crisis_din, activos_sel, umbral_vix,
                                    rango_fechas, regimen_filtro, foco)
        styles.lectura(bloque.eyebrow, bloque.lead, bloque.puntos)

        precios_norm = precios / precios.bfill().iloc[0] * 100
        fig1 = make_subplots(
            rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.07,
        )

        crisis_bool = crisis_din.reindex(precios.index)
        _bandas_crisis(fig1, crisis_bool, row=1, col=1)
        _bandas_crisis(fig1, crisis_bool, row=2, col=1)

        for activo in activos_sel:
            fig1.add_trace(
                go.Scatter(
                    x=precios_norm.index, y=precios_norm[activo], mode="lines",
                    name=ETIQUETAS_ACTIVO.get(activo, activo),
                    line=dict(color=styles.color_activo(activo), width=_ancho(activo, foco)),
                    opacity=_opacidad(activo, foco),
                    hovertemplate=f"{ETIQUETAS_ACTIVO.get(activo, activo)}<br>%{{x|%Y-%m-%d}}: %{{y:.1f}}<extra></extra>",
                ),
                row=1, col=1,
            )
        fig1.add_hline(y=100, line_dash="dot", line_color=styles.GRID, line_width=1.5, row=1, col=1)

        fig1.add_trace(
            go.Scatter(
                x=vix.index, y=vix, mode="lines", name="VIX",
                line=dict(color=styles.DEEP, width=1.4),
                fill="tozeroy", fillcolor="rgba(50, 96, 128, 0.08)",
                hovertemplate="VIX<br>%{x|%Y-%m-%d}: %{y:.1f}<extra></extra>", showlegend=False,
            ),
            row=2, col=1,
        )
        fig1.add_hline(
            y=umbral_vix, line_dash="dash", line_color=styles.CRISIS, line_width=1.5, row=2, col=1,
            annotation_text=f"umbral {umbral_vix}", annotation_position="top left",
            annotation_font=dict(color=styles.CRISIS, size=11),
        )

        fig1.update_yaxes(styles.eje(title_text="Precio (base 100)"), row=1, col=1)
        fig1.update_yaxes(styles.eje(title_text="VIX"), row=2, col=1)
        fig1.update_xaxes(styles.eje(showgrid=False), row=1, col=1)
        fig1.update_xaxes(styles.eje(), row=2, col=1)
        fig1.update_layout(
            height=540,
            **styles.PLOTLY_BASE,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0,
                        font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
            margin=dict(t=36, b=10, l=10, r=10),
        )
        st.plotly_chart(fig1, width="stretch")


# ============================================================================
# Vista 2 - Volatilidad por regimen
# ============================================================================
def render_volatilidad(vol, regimen_din, regimen_filtro, activos_sel, foco):
    with styles.card("volatilidad"):
        styles.icon_corner("▮")
        styles.section_title(
            "Volatilidad por regimen",
            "Volatilidad realizada anualizada (desviacion movil de 21 dias × √252), promedio "
            "por activo en calma y en crisis.",
        )

        bloque = narrativa.volatilidad(vol, regimen_din, regimen_filtro, activos_sel, foco)
        styles.lectura(bloque.eyebrow, bloque.lead, bloque.puntos)

        vol_calma = (vol[regimen_din.reindex(vol.index) == "Calma"].mean() * 100).reindex(activos_sel)
        vol_crisis = (vol[regimen_din.reindex(vol.index) == "Crisis"].mean() * 100).reindex(activos_sel)

        etiquetas_x = [ETIQUETAS_ACTIVO.get(a, a) for a in activos_sel]
        # Resaltado enlazado: la barra del activo en foco se opaca menos que el resto.
        op = [1.0 if (foco == SIN_FOCO or a == foco) else 0.25 for a in activos_sel]

        fig2 = go.Figure()
        if regimen_filtro in ("Ambos", "Calma"):
            fig2.add_trace(go.Bar(
                x=etiquetas_x, y=vol_calma.values, name="Calma", marker_color=styles.CALMA,
                marker_opacity=op, marker_line=dict(color="white", width=1.5),
                text=[f"{v:.0f}" if pd.notna(v) else "" for v in vol_calma.values],
                textposition="outside", textfont=dict(size=10, color=styles.TEXT_MUTED),
                hovertemplate="%{x}<br>Calma: %{y:.1f}%<extra></extra>",
            ))
        if regimen_filtro in ("Ambos", "Crisis"):
            fig2.add_trace(go.Bar(
                x=etiquetas_x, y=vol_crisis.values, name="Crisis", marker_color=styles.CRISIS,
                marker_opacity=op, marker_line=dict(color="white", width=1.5),
                text=[f"{v:.0f}" if pd.notna(v) else "" for v in vol_crisis.values],
                textposition="outside", textfont=dict(size=10, color=styles.TEXT_MUTED),
                hovertemplate="%{x}<br>Crisis: %{y:.1f}%<extra></extra>",
            ))

        titulo_vol = "La volatilidad se multiplica en crisis"
        mult = (vol_crisis / vol_calma).replace([np.inf, -np.inf], np.nan).dropna()
        if len(mult) > 0:
            top = mult.sort_values(ascending=False).head(2)
            titulo_vol += "  ·  " + ", ".join(f"{a} ×{v:.1f}" for a, v in top.items())

        fig2.update_layout(
            title=dict(text=titulo_vol,
                       font=dict(family=styles.FONT_SERIF, size=17, color=styles.DEEP)),
            barmode="group", bargap=0.3, bargroupgap=0.06,
            **styles.PLOTLY_BASE,
            yaxis=styles.eje(title="Volatilidad anualizada (%)"),
            xaxis=styles.eje(showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
            height=470,
            margin=dict(t=72, b=10, l=10, r=10),
        )
        st.plotly_chart(fig2, width="stretch")

    with styles.card("vol-tabla", variant="soft"):
        styles.section_title("Datos de respaldo", "Los mismos numeros del grafico, para citar sin estimar a ojo.")
        st.dataframe(bloque.tabla, width="stretch", hide_index=True)


# ============================================================================
# Vista 3 - Matriz de correlacion por regimen (MVP) + correlacion rolling
# ============================================================================
def render_correlacion(retornos, regimen_din, regimen_filtro, activos_sel, min_obs_corr,
                       crisis_din, umbral_vix, foco):
    with styles.card("correlacion", variant="mvp"):
        styles.section_title(
            "Matriz de correlacion por regimen",
            "Escala divergente centrada en 0 y segura para daltonismo: frio = cobertura, "
            "neutro = independencia, calido = se mueven juntos.",
            badge_html=styles.badge("MVP · prioridad #1", variant="red"),
        )

        if len(activos_sel) < 2:
            st.info("Seleccione al menos 2 activos para calcular la matriz de correlacion.")
            return

        bloque = narrativa.correlacion(retornos, regimen_din, regimen_filtro, activos_sel,
                                       min_obs_corr, foco)
        styles.lectura(bloque.eyebrow, bloque.lead, bloque.puntos)

        etiquetas_x = [ETIQUETAS_ACTIVO.get(a, a) for a in activos_sel]
        regimen_ret = regimen_din.reindex(retornos.index)
        corr_calma = retornos[regimen_ret == "Calma"].corr(min_periods=min_obs_corr)
        corr_crisis = retornos[regimen_ret == "Crisis"].corr(min_periods=min_obs_corr)

        n_calma = int((regimen_ret == "Calma").sum())
        n_crisis = int((regimen_ret == "Crisis").sum())
        if n_crisis < min_obs_corr:
            st.warning(
                f"Solo hay {n_crisis} dias de Crisis en el rango/umbral seleccionado "
                f"(minimo recomendado: {min_obs_corr}). La matriz de Crisis puede ser poco "
                f"confiable o mostrar celdas vacias."
            )

        paneles = []
        if regimen_filtro in ("Ambos", "Calma"):
            paneles.append(("CALMA", corr_calma, n_calma))
        if regimen_filtro in ("Ambos", "Crisis"):
            paneles.append(("CRISIS", corr_crisis, n_crisis))

        fig3 = make_subplots(
            rows=1, cols=len(paneles), horizontal_spacing=0.13,
            subplot_titles=[f"{nombre}  ·  n={n} dias" for nombre, _, n in paneles],
        )
        for col_idx, (_, corr, _) in enumerate(paneles, start=1):
            fig3.add_trace(
                go.Heatmap(
                    z=corr.values, x=etiquetas_x, y=etiquetas_x, coloraxis="coloraxis",
                    xgap=2, ygap=2,
                    texttemplate="%{z:.2f}", textfont=dict(size=10),
                    hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
                ),
                row=1, col=col_idx,
            )
            fig3.update_yaxes(autorange="reversed", showgrid=False,
                              tickfont=dict(size=10, color=styles.TEXT_MUTED), row=1, col=col_idx)
            fig3.update_xaxes(showgrid=False, tickangle=-35,
                              tickfont=dict(size=10, color=styles.TEXT_MUTED), row=1, col=col_idx)
            # Resaltado enlazado: recuadro sobre la fila/columna del activo en foco.
            if foco != SIN_FOCO and foco in activos_sel:
                j = activos_sel.index(foco)
                for x0, x1, y0, y1 in [
                    (-0.5, len(activos_sel) - 0.5, j - 0.5, j + 0.5),
                    (j - 0.5, j + 0.5, -0.5, len(activos_sel) - 0.5),
                ]:
                    fig3.add_shape(
                        type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                        line=dict(color=styles.DEEP, width=2.2), fillcolor="rgba(0,0,0,0)",
                        row=1, col=col_idx,
                    )

        fig3.update_layout(
            coloraxis=dict(colorscale=styles.ESCALA_CORR, cmin=-1, cmax=1,
                           colorbar=dict(title=dict(text="ρ", font=dict(size=12)),
                                         thickness=12, outlinewidth=0, len=0.85,
                                         tickfont=dict(size=10, color=styles.TEXT_MUTED))),
            **styles.PLOTLY_BASE,
            height=540,
            margin=dict(t=54, b=10, l=10, r=10),
        )
        fig3.update_annotations(font=dict(family=styles.FONT_SERIF, size=13, color=styles.DEEP))
        st.plotly_chart(fig3, width="stretch")

        if bloque.tabla is not None:
            styles.section_title(bloque.tabla_titulo, "")
            st.dataframe(bloque.tabla, width="stretch", hide_index=True)

    # --- Correlacion rolling de un par elegido ---------------------------------
    with styles.card("corr-par"):
        styles.icon_corner("∿")
        styles.section_title(
            "Correlacion rolling de un par",
            "El mapa de calor da un promedio por regimen; esta linea muestra cuando ocurre "
            "el acoplamiento a lo largo del tiempo.",
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

        bloque_par = narrativa.correlacion_par(retornos, regimen_din, par_a, par_b, ventana,
                                               crisis_din)
        styles.lectura(bloque_par.eyebrow, bloque_par.lead, bloque_par.puntos)

        roll = retornos[par_a].rolling(ventana, min_periods=int(ventana * 0.6)).corr(retornos[par_b])
        media_calma = roll[regimen_din.reindex(roll.index) == "Calma"].mean()
        media_crisis = roll[regimen_din.reindex(roll.index) == "Crisis"].mean()

        figp = go.Figure()
        _bandas_crisis(figp, crisis_din.reindex(roll.index))
        figp.add_hline(y=0, line_color=styles.GRID, line_width=1.5)
        figp.add_trace(go.Scatter(
            x=roll.index, y=roll, mode="lines", line=dict(color=styles.DEEP, width=2),
            name=f"{par_a}–{par_b}",
            hovertemplate=f"{par_a}–{par_b}<br>%{{x|%Y-%m-%d}}: %{{y:.2f}}<extra></extra>",
        ))
        for y, txt, col in [(media_calma, "media calma", styles.CALMA),
                            (media_crisis, "media crisis", styles.CRISIS)]:
            if pd.notna(y):
                figp.add_hline(y=y, line_dash="dot", line_color=col, line_width=1.5,
                               annotation_text=f"{txt}: {y:.2f}",
                               annotation_font=dict(color=col, size=11),
                               annotation_position="top left")
        figp.update_layout(
            **styles.PLOTLY_BASE,
            yaxis=styles.eje(title="Correlacion rolling", range=[-1, 1]),
            xaxis=styles.eje(),
            height=350, margin=dict(t=24, b=10, l=10, r=10), showlegend=False,
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
        rec_txt = f"{(recuperado.index[0] - valle).days} d" if len(recuperado) else "sin recuperar"
        filas.append({
            "Activo": ETIQUETAS_ACTIVO.get(a, a),
            "_codigo": a,
            "Peor drawdown": peor * 100,
            "Fecha valle": valle.date().isoformat(),
            "Recuperacion": rec_txt,
        })
    if not filas:
        return pd.DataFrame(columns=["Activo", "_codigo", "Peor drawdown",
                                     "Fecha valle", "Recuperacion"])
    return pd.DataFrame(filas).sort_values("Peor drawdown")


def render_drawdown(drawdown, crisis_din, activos_sel, regimen_filtro, foco):
    dd = drawdown[activos_sel]
    stats = _stats_drawdown(dd)

    col1, col2, col3 = st.columns(3)
    if not stats.empty:
        peor_fila = stats.iloc[0]
        sin_rec = stats[stats["Recuperacion"] == "sin recuperar"]
        with col1:
            with styles.card("dd-peor", variant="dark"):
                styles.icon_corner("↓")
                styles.hero_metric(f"{peor_fila['Peor drawdown']:.1f}%", "PEOR DRAWDOWN",
                                   sub=f"{peor_fila['Activo']} · valle {peor_fila['Fecha valle']}")
        with col2:
            with styles.card("dd-prom"):
                styles.hero_metric(f"{stats['Peor drawdown'].mean():.1f}%", "PEOR CAIDA PROMEDIO",
                                   sub=f"media de los {len(stats)} activos en vista")
        with col3:
            with styles.card("dd-sinrec"):
                styles.hero_metric(f"{len(sin_rec)}", "SIN RECUPERAR",
                                   sub="no vuelven a su maximo previo dentro del rango")

    with styles.card("drawdown-chart"):
        styles.icon_corner("~")
        styles.section_title(
            "Drawdown (underwater plot)",
            "Distancia de cada activo respecto a su propio maximo previo. Cero = en maximos.",
        )

        bloque = narrativa.drawdown(dd, stats, crisis_din, activos_sel, foco)
        styles.lectura(bloque.eyebrow, bloque.lead, bloque.puntos)

        fig4 = go.Figure()
        _bandas_crisis(fig4, crisis_din.reindex(dd.index))
        for a in activos_sel:
            fig4.add_trace(go.Scatter(
                x=dd.index, y=dd[a] * 100, mode="lines", name=ETIQUETAS_ACTIVO.get(a, a),
                line=dict(color=styles.color_activo(a), width=_ancho(a, foco, base=1.5)),
                opacity=_opacidad(a, foco),
                hovertemplate=f"{ETIQUETAS_ACTIVO.get(a, a)}<br>%{{x|%Y-%m-%d}}: %{{y:.1f}}%<extra></extra>",
            ))
        fig4.update_layout(
            **styles.PLOTLY_BASE,
            hovermode="x unified",
            yaxis=styles.eje(title="Drawdown (%)", rangemode="tozero"),
            xaxis=styles.eje(),
            legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0,
                        font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
            height=470, margin=dict(t=36, b=10, l=10, r=10),
        )
        st.plotly_chart(fig4, width="stretch")

    with styles.card("drawdown-rank", variant="soft"):
        styles.section_title(
            "Ranking de peor drawdown y recuperacion",
            "De la peor caida a la menos mala. 'Recuperacion' = dias desde el valle hasta "
            "volver al maximo previo.",
        )
        if bloque.tabla is not None:
            st.dataframe(bloque.tabla, width="stretch", hide_index=True)


# ============================================================================
# Vista 5 - Distribucion de retornos (colas gordas por regimen)
# ============================================================================
def render_distribucion(retornos, regimen_din, regimen_filtro, activos_sel, foco):
    with styles.card("distribucion"):
        styles.icon_corner("◑")
        styles.section_title(
            "Distribucion de retornos por regimen",
            "Violines de retornos diarios (%) por activo: mitad fria calma, mitad calida crisis.",
        )

        bloque = narrativa.distribucion(retornos, regimen_din, regimen_filtro, activos_sel, foco)
        styles.lectura(bloque.eyebrow, bloque.lead, bloque.puntos)

        regimen_ret = regimen_din.reindex(retornos.index)

        fig5 = go.Figure()
        for a in activos_sel:
            for reg, color in [("Calma", styles.CALMA), ("Crisis", styles.CRISIS)]:
                if regimen_filtro not in ("Ambos", reg):
                    continue
                serie = (retornos[a][regimen_ret == reg] * 100).dropna()
                if serie.empty:
                    continue
                op = 1.0 if (foco == SIN_FOCO or a == foco) else 0.25
                fig5.add_trace(go.Violin(
                    x=[ETIQUETAS_ACTIVO.get(a, a)] * len(serie), y=serie.values,
                    name=reg, legendgroup=reg, scalegroup=reg, showlegend=False,
                    side="negative" if reg == "Calma" else "positive",
                    line=dict(color=color, width=1.2), fillcolor=color, opacity=op * 0.75,
                    points=False, meanline_visible=True, width=0.9,
                    hovertemplate=f"{ETIQUETAS_ACTIVO.get(a, a)} · {reg}<br>%{{y:.2f}}%<extra></extra>",
                ))
        # Trazas fantasma solo para la leyenda Calma/Crisis
        for reg, color in [("Calma", styles.CALMA), ("Crisis", styles.CRISIS)]:
            if regimen_filtro in ("Ambos", reg):
                fig5.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                                          marker=dict(color=color, size=10), name=reg))

        fig5.update_layout(
            violinmode="overlay",
            **styles.PLOTLY_BASE,
            yaxis=styles.eje(title="Retorno diario (%)", zeroline=True, zerolinecolor=styles.GRID,
                             zerolinewidth=1.5),
            xaxis=styles.eje(showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
            height=490, margin=dict(t=36, b=10, l=10, r=10),
        )
        st.plotly_chart(fig5, width="stretch")

    with styles.card("dist-colas", variant="soft"):
        styles.section_title(
            "Cuantificacion de las colas",
            "Curtosis en exceso > 0 = colas mas gordas que una normal. El peor dia por regimen "
            "muestra cuanto peor puede ser un solo dia en crisis.",
        )
        st.dataframe(bloque.tabla, width="stretch", hide_index=True)


# ============================================================================
# Vista 6 - Red de contagio (opcional / stretch)
# ============================================================================
def render_contagio(retornos, regimen_din, activos_sel, foco):
    with styles.card("contagio"):
        styles.icon_corner("◈")
        styles.section_title(
            "Red de contagio",
            "Grafo de correlaciones: cada nodo es un activo y cada arista un par por encima "
            "del umbral. Al pasar de calma a crisis el mercado se vuelve un solo bloque.",
            badge_html=styles.badge("opcional · stretch", variant="amber"),
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

        bloque = narrativa.contagio(retornos, regimen_din, activos_sel, umbral_arista,
                                    regimen_red, MIN_OBS_CORR, foco)
        styles.lectura(bloque.eyebrow, bloque.lead, bloque.puntos)

        regimen_ret = regimen_din.reindex(retornos.index)
        corr = retornos[activos_sel][regimen_ret == regimen_red].corr(min_periods=MIN_OBS_CORR)

        n = len(activos_sel)
        angulos = np.linspace(np.pi / 2, np.pi / 2 + 2 * np.pi, n, endpoint=False)
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
                col = styles.CRISIS if r > 0 else styles.CALMA
                resaltar = foco == SIN_FOCO or foco in (a, b)
                fig6.add_trace(go.Scatter(
                    x=[x0, x1], y=[y0, y1], mode="lines",
                    line=dict(color=col, width=0.8 + 4.5 * abs(r)),
                    opacity=(0.55 if resaltar else 0.08),
                    hoverinfo="text", text=f"{a}–{b}: {r:.2f}", showlegend=False,
                ))

        for a in activos_sel:
            x, y = pos[a]
            foco_nodo = foco == SIN_FOCO or a == foco
            fig6.add_trace(go.Scatter(
                x=[x], y=[y], mode="markers+text", text=[a], textposition="middle center",
                textfont=dict(color="white", size=9, family=styles.FONT_SANS),
                marker=dict(size=44, color=styles.color_activo(a),
                            line=dict(color=styles.DEEP if a == foco and foco != SIN_FOCO else "white",
                                      width=3 if a == foco and foco != SIN_FOCO else 2)),
                opacity=(1.0 if foco_nodo else 0.28),
                hovertemplate=f"{ETIQUETAS_ACTIVO.get(a, a)}<extra></extra>", showlegend=False,
            ))

        fig6.update_layout(
            **styles.PLOTLY_BASE,
            xaxis=dict(visible=False, range=[-1.4, 1.4]),
            yaxis=dict(visible=False, range=[-1.4, 1.4], scaleanchor="x", scaleratio=1),
            height=560, margin=dict(t=10, b=10, l=10, r=10),
        )
        st.plotly_chart(fig6, width="stretch")
        styles.note(
            f"<b>{n_aristas}</b> aristas sobre el umbral |ρ|≥{umbral_arista:.2f} en regimen "
            f"<b>{regimen_red}</b>. Tono calido = correlacion positiva (se mueven juntos), "
            f"frio = negativa (cobertura). El grosor codifica la fuerza del vinculo."
        )

        if bloque.tabla is not None:
            styles.section_title(bloque.tabla_titulo, "")
            st.dataframe(bloque.tabla, width="stretch", hide_index=True)


# ============================================================================
# Self-report: PDF con las SEIS pantallas, al pie de cada vista
# ============================================================================
def construir_bloques(ctx):
    """Calcula la lectura guiada de las seis pantallas con los parametros actuales.

    Se ejecuta con independencia de la vista visible: el PDF siempre trae el
    tablero completo. Los modulos interactivos (par de correlacion rolling, umbral
    de contagio) usan lo que el usuario haya dejado en session_state, o su valor
    por defecto si aun no ha entrado a esa pantalla.
    """
    bloques = [
        narrativa.overview(ctx["precios"], ctx["vix"], ctx["crisis_din"], ctx["activos_sel"],
                           ctx["umbral_vix"], ctx["rango_fechas"], ctx["regimen_filtro"],
                           ctx["foco"]),
        narrativa.volatilidad(ctx["vol"], ctx["regimen_din"], ctx["regimen_filtro"],
                              ctx["activos_sel"], ctx["foco"]),
    ]

    if len(ctx["activos_sel"]) >= 2:
        bloques.append(narrativa.correlacion(
            ctx["retornos"], ctx["regimen_din"], ctx["regimen_filtro"], ctx["activos_sel"],
            MIN_OBS_CORR, ctx["foco"]))

        par_a = st.session_state.get("par_a")
        par_b = st.session_state.get("par_b")
        if par_a not in ctx["activos_sel"]:
            par_a = ctx["activos_sel"][0]
        if par_b not in ctx["activos_sel"] or par_b == par_a:
            par_b = next(a for a in ctx["activos_sel"] if a != par_a)
        bloques.append(narrativa.correlacion_par(
            ctx["retornos"], ctx["regimen_din"], par_a, par_b,
            st.session_state.get("corr_win", 63), ctx["crisis_din"]))

    dd = ctx["drawdown"][ctx["activos_sel"]]
    bloques.append(narrativa.drawdown(dd, _stats_drawdown(dd), ctx["crisis_din"],
                                      ctx["activos_sel"], ctx["foco"]))
    bloques.append(narrativa.distribucion(ctx["retornos"], ctx["regimen_din"],
                                          ctx["regimen_filtro"], ctx["activos_sel"], ctx["foco"]))

    if len(ctx["activos_sel"]) >= 2:
        bloques.append(narrativa.contagio(
            ctx["retornos"], ctx["regimen_din"], ctx["activos_sel"],
            st.session_state.get("contagio_umbral", 0.5),
            st.session_state.get("contagio_regimen", "Crisis"),
            MIN_OBS_CORR, ctx["foco"]))

    return bloques


def render_self_report(ctx, vista_actual):
    """Bloque de descarga al pie de cada pantalla."""
    styles.rule()
    with styles.card(vista_actual.lower(), variant="report"):
        izq, der = st.columns([3, 2], vertical_alignment="center")
        with izq:
            styles.section_title("Self-report")
            st.markdown(
                '<div class="section-caption">Descarga un PDF con las <b>seis pantallas</b> '
                '&mdash; no solo esta &mdash; con los datos y los insights ya redactados '
                'para la seleccion de activos, el rango, el umbral de VIX y el filtro de '
                'regimen que tienes puestos ahora mismo.</div>',
                unsafe_allow_html=True,
            )
        with der:
            firma = (
                f"{sorted(ctx['activos_sel'])}|{ctx['rango_fechas']}|{ctx['umbral_vix']}"
                f"|{ctx['regimen_filtro']}|{ctx['foco']}"
                f"|{st.session_state.get('par_a')}|{st.session_state.get('par_b')}"
                f"|{st.session_state.get('corr_win')}"
                f"|{st.session_state.get('contagio_umbral')}"
                f"|{st.session_state.get('contagio_regimen')}"
            )
            if st.session_state.get("_firma_pdf") != firma:
                with st.spinner("Preparando el informe..."):
                    bloques = construir_bloques(ctx)
                    params = narrativa.resumen_parametros(
                        ctx["activos_sel"], ctx["rango_fechas"], ctx["umbral_vix"],
                        ctx["regimen_filtro"], ctx["foco"], len(ctx["precios"]),
                        100 * ctx["crisis_din"].reindex(ctx["precios"].index).fillna(False).mean(),
                    )
                    st.session_state["_pdf"] = reporte.generar_pdf(params, bloques, vista_actual)
                    st.session_state["_firma_pdf"] = firma

            nombre = (f"self-report_riesgo-mercado_"
                      f"{ctx['rango_fechas'][0]}_{ctx['rango_fechas'][1]}.pdf")
            st.download_button(
                "⤓  Descargar informe en PDF",
                data=st.session_state["_pdf"],
                file_name=nombre,
                mime="application/pdf",
                width="stretch",
                key=f"dl_{vista_actual}",
            )
            st.markdown(
                f'<div class="hero-sub">{len(st.session_state["_pdf"]) / 1024:.0f} KB · '
                f'{len(ctx["activos_sel"])} activos · umbral VIX {ctx["umbral_vix"]}</div>',
                unsafe_allow_html=True,
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

ctx = dict(
    precios=precios, vix=vix, retornos=retornos, vol=vol, drawdown=drawdown,
    crisis_din=crisis_din, regimen_din=regimen_din, activos_sel=activos_sel,
    umbral_vix=umbral_vix, rango_fechas=rango_fechas, regimen_filtro=regimen_filtro, foco=foco,
)

# --- Topbar: titulo + nav + subtitulo ----------------------------------------
with st.container(key="topbar", horizontal=True, vertical_alignment="center"):
    st.markdown(
        '<div class="topbar-title">Anatomia del riesgo '
        '<span class="accent">&middot; Calma vs Crisis</span></div>',
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
    render_overview(precios, vix, crisis_din, activos_sel, umbral_vix, rango_fechas,
                    regimen_filtro, foco)
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

render_self_report(ctx, seleccion)

st.caption(
    "Datos reales de Yahoo Finance (2018–2026). "
    "Limitaciones de datos documentadas en el README y en la nota metodologica del informe."
)
