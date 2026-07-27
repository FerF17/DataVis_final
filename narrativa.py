"""
narrativa.py
Descripciones parametrizadas ("lectura guiada") de cada vista del dashboard.

Objetivo: que el lector entienda lo que esta viendo SIN importar que ETF o
combinacion de ETFs haya seleccionado, que rango de fechas, que umbral de VIX o
que filtro de regimen tenga puesto. Nada de este modulo esta escrito a mano para
SPY/TLT/etc.: cada frase se resuelve en vivo contra los datos filtrados que
recibe la vista.

Cada funcion publica devuelve un `Bloque`:

    Bloque(
        titulo   -- nombre de la pantalla
        eyebrow  -- etiqueta corta del bloque de lectura
        lead     -- frase principal ya resuelta
        puntos   -- bullets en HTML ligero (<b>, <b class="num">)
        insights -- las mismas conclusiones en texto plano, para el PDF
        tabla    -- DataFrame de respaldo (o None)
        tabla_titulo
    )

`styles.lectura()` lo pinta en pantalla; `reporte.py` lo vuelca al PDF. Una sola
fuente de verdad para ambos: lo que el usuario lee en la pantalla es
exactamente lo que se descarga.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

ETIQUETAS_ACTIVO = {
    "SPY": "SPY (Acciones)", "QQQ": "QQQ (Tech)", "TLT": "TLT (Bonos LP)",
    "GLD": "GLD (Oro)", "HYG": "HYG (HY Credito)", "VNQ": "VNQ (Real Estate)",
    "EEM": "EEM (Emergentes)", "DBC": "DBC (Commodities)", "UUP": "UUP (Dolar)",
    "BTC-USD": "BTC-USD (Cripto)",
}

SIN_FOCO = "(ninguno)"


def etiqueta(a: str) -> str:
    return ETIQUETAS_ACTIVO.get(a, a)


@dataclass
class Bloque:
    titulo: str
    eyebrow: str
    lead: str
    puntos: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    tabla: Optional[pd.DataFrame] = None
    tabla_titulo: str = ""


# ---------------------------------------------------------------------------
# Helpers de formato y de texto plano
# ---------------------------------------------------------------------------
def n(valor, fmt="{:.2f}") -> str:
    """Numero resaltado. NaN -> guion largo, para no imprimir 'nan' jamas."""
    if valor is None or (isinstance(valor, float) and not np.isfinite(valor)):
        return '<b class="num">—</b>'
    return f'<b class="num">{fmt.format(valor)}</b>'


def _plano(html: str) -> str:
    """Convierte un bullet HTML a texto plano legible (para el PDF y los tests)."""
    import html as _html
    import re
    txt = re.sub(r"<[^>]+>", "", html)
    return _html.unescape(txt).replace(" ", " ").strip()


def _listado(activos: List[str], maximo: int = 5) -> str:
    """'SPY, QQQ y TLT' / 'SPY, QQQ, TLT, GLD, HYG y 5 mas'.

    Si solo sobra uno, se lista completo: "y 1 mas" es peor que decir su nombre.
    """
    activos = [str(a) for a in activos]
    if not activos:
        return "ninguno"
    if len(activos) == 1:
        return activos[0]
    if len(activos) <= maximo + 1:
        return ", ".join(activos[:-1]) + " y " + activos[-1]
    return ", ".join(activos[:maximo]) + f" y {len(activos) - maximo} mas"


def _frase_regimen(regimen_filtro: str) -> str:
    if regimen_filtro == "Ambos":
        return "los dos regimenes (calma y crisis)"
    return f"solo el regimen de <b>{regimen_filtro.lower()}</b>"


def _episodios(crisis_bool: pd.Series):
    """Lista de (inicio, fin, n_dias) de cada tramo continuo de crisis."""
    crisis_bool = crisis_bool.fillna(False)
    if not crisis_bool.any():
        return []
    bloques = (crisis_bool != crisis_bool.shift()).cumsum()
    out = []
    for _, g in crisis_bool[crisis_bool].groupby(bloques[crisis_bool]):
        out.append((g.index.min(), g.index.max(), len(g)))
    return out


def _cierre(bloque: Bloque) -> Bloque:
    """Rellena `insights` en texto plano a partir de lead + puntos."""
    bloque.insights = [_plano(bloque.lead)] + [_plano(p) for p in bloque.puntos]
    return bloque


# ---------------------------------------------------------------------------
# Encabezado: los parametros activos, en una frase
# ---------------------------------------------------------------------------
def resumen_parametros(activos_sel, rango_fechas, umbral_vix, regimen_filtro,
                       foco, n_dias, pct_crisis) -> dict:
    return {
        "activos": list(activos_sel),
        "n_activos": len(activos_sel),
        "rango": f"{rango_fechas[0]} a {rango_fechas[1]}",
        "umbral_vix": umbral_vix,
        "regimen_filtro": regimen_filtro,
        "foco": "ninguno" if foco == SIN_FOCO else etiqueta(foco),
        "n_dias": int(n_dias),
        "pct_crisis": float(pct_crisis),
    }


# ---------------------------------------------------------------------------
# Vista 1 - Overview
# ---------------------------------------------------------------------------
def overview(precios, vix, crisis_din, activos_sel, umbral_vix, rango_fechas,
             regimen_filtro, foco) -> Bloque:
    crisis_bool = crisis_din.reindex(precios.index).fillna(False)
    pct_crisis = 100 * crisis_bool.mean() if len(crisis_bool) else float("nan")
    eps = _episodios(crisis_bool)

    norm = precios / precios.bfill().iloc[0] * 100
    final = norm.iloc[-1].dropna() if len(norm) else pd.Series(dtype=float)

    lead = (
        f"Cada linea es un ETF reescalado a <b>base 100</b> el "
        f"{precios.index.min().date()}: lo que compara el grafico es <b>rendimiento "
        f"relativo</b>, no precio. Hay {n(len(activos_sel), '{:.0f}')} activos en pantalla "
        f"({_listado(activos_sel)}) sobre {n(len(precios), '{:,.0f}')} dias bursatiles, "
        f"de los cuales {n(pct_crisis, '{:.1f}')}% quedan clasificados como crisis con "
        f"el umbral VIX &gt; {n(umbral_vix, '{:.0f}')} que fijaste."
    )

    puntos = []
    if len(final) >= 1:
        mejor, peor = final.idxmax(), final.idxmin()
        puntos.append(
            f"En este rango el mejor comportamiento acumulado es de <b>{etiqueta(mejor)}</b>, "
            f"que termina en {n(final[mejor], '{:.0f}')} (es decir "
            f"{n(final[mejor] - 100, '{:+.0f}')}% desde el inicio del rango); el peor es "
            f"<b>{etiqueta(peor)}</b> en {n(final[peor], '{:.0f}')} "
            f"({n(final[peor] - 100, '{:+.0f}')}%). Una linea por encima de 100 gano; "
            f"por debajo, perdio."
        )
    if len(vix.dropna()):
        pico = vix.idxmax()
        puntos.append(
            f"El panel inferior es el <b>VIX</b>, el termometro de miedo que decide el "
            f"regimen. Su maximo en el rango es {n(vix.max(), '{:.1f}')} el "
            f"{pico.date()}, contra una media de {n(vix.mean(), '{:.1f}')}. "
            f"La linea punteada marca tu umbral de {n(umbral_vix, '{:.0f}')}."
        )
    if eps:
        mas_largo = max(eps, key=lambda e: e[2])
        puntos.append(
            f"Las bandas calidas verticales son los {n(len(eps), '{:.0f}')} episodios de "
            f"crisis del rango; el mas largo va del {mas_largo[0].date()} al "
            f"{mas_largo[1].date()} ({n(mas_largo[2], '{:.0f}')} dias seguidos). "
            f"Fijate si las lineas caen <b>a la vez</b> dentro de esas bandas: esa "
            f"simultaneidad es justamente la tesis del tablero."
        )
    else:
        puntos.append(
            f"Con el umbral actual (VIX &gt; {n(umbral_vix, '{:.0f}')}) <b>no hay ningun dia "
            f"de crisis</b> en el rango elegido, por eso no ves bandas sombreadas. "
            f"Baja el umbral o amplia el rango para que aparezcan."
        )
    if foco != SIN_FOCO and foco in activos_sel and foco in final.index:
        puntos.append(
            f"Tienes <b>{etiqueta(foco)}</b> en foco: es la unica linea a plena opacidad "
            f"y cierra el rango en {n(final[foco], '{:.0f}')}. Ese mismo resaltado te "
            f"sigue en las otras cinco pantallas."
        )
    if regimen_filtro != "Ambos":
        puntos.append(
            f"Ojo: el filtro de regimen ({regimen_filtro}) no recorta esta serie temporal "
            f"—aqui siempre ves el rango completo—, pero si condiciona las pantallas "
            f"de volatilidad, correlacion y distribucion."
        )

    tabla = None
    if len(final):
        tabla = pd.DataFrame({
            "Activo": [etiqueta(a) for a in final.index],
            "Base 100 final": [f"{v:.1f}" for v in final.values],
            "Retorno del rango": [f"{v - 100:+.1f}%" for v in final.values],
        })

    return _cierre(Bloque(
        titulo="Overview temporal",
        eyebrow="Como leer esta pantalla",
        lead=lead, puntos=puntos, tabla=tabla,
        tabla_titulo="Rendimiento acumulado en el rango (base 100)",
    ))


# ---------------------------------------------------------------------------
# Vista 2 - Volatilidad
# ---------------------------------------------------------------------------
def volatilidad(vol, regimen_din, regimen_filtro, activos_sel, foco) -> Bloque:
    reg = regimen_din.reindex(vol.index)
    v_calma = (vol[reg == "Calma"].mean() * 100).reindex(activos_sel)
    v_crisis = (vol[reg == "Crisis"].mean() * 100).reindex(activos_sel)
    mult = (v_crisis / v_calma).replace([np.inf, -np.inf], np.nan)
    mult_ok = mult.dropna()

    lead = (
        f"Cada par de barras es un ETF: la barra fria es su <b>volatilidad anualizada "
        f"media en calma</b> y la calida, la misma medida <b>en crisis</b>. Se calcula "
        f"con la desviacion estandar movil de 21 dias de los retornos, anualizada por "
        f"raiz de 252. Estas viendo {n(len(activos_sel), '{:.0f}')} activos "
        f"({_listado(activos_sel)}) y el filtro muestra {_frase_regimen(regimen_filtro)}."
    )

    puntos = []
    if len(mult_ok):
        top = mult_ok.sort_values(ascending=False)
        a1 = top.index[0]
        puntos.append(
            f"El que mas multiplica su riesgo al entrar en panico es <b>{etiqueta(a1)}</b>: "
            f"pasa de {n(v_calma[a1], '{:.1f}')}% a {n(v_crisis[a1], '{:.1f}')}% anualizado, "
            f"un factor de x{n(top.iloc[0], '{:.1f}')}."
        )
        a2 = top.index[-1]
        puntos.append(
            f"El que menos lo multiplica es <b>{etiqueta(a2)}</b> (x{n(top.iloc[-1], '{:.1f}')}, "
            f"de {n(v_calma[a2], '{:.1f}')}% a {n(v_crisis[a2], '{:.1f}')}%). Multiplicar "
            f"poco no es lo mismo que ser tranquilo: mira tambien la altura absoluta de "
            f"su barra."
        )
        puntos.append(
            f"En promedio, los activos en pantalla multiplican su volatilidad por "
            f"x{n(mult_ok.mean(), '{:.1f}')} al pasar de calma a crisis, y "
            f"{n((mult_ok > 1).sum(), '{:.0f}')} de {n(len(mult_ok), '{:.0f}')} la aumentan. "
            f"Que casi todos suban a la vez es la primera senal de que el riesgo no se "
            f"reparte: llega junto."
        )
    if len(v_crisis.dropna()):
        abs_max = v_crisis.dropna().idxmax()
        puntos.append(
            f"En terminos absolutos, el activo mas volatil en crisis es "
            f"<b>{etiqueta(abs_max)}</b> con {n(v_crisis[abs_max], '{:.1f}')}% anualizado. "
            f"Como referencia: 20% anual equivale a moverse alrededor de ±1.3% en un dia "
            f"tipico."
        )
    if foco != SIN_FOCO and foco in mult_ok.index:
        pos = int((mult_ok.sort_values(ascending=False).index == foco).argmax()) + 1
        puntos.append(
            f"<b>{etiqueta(foco)}</b>, tu activo en foco, ocupa el puesto "
            f"{n(pos, '{:.0f}')} de {n(len(mult_ok), '{:.0f}')} por multiplicador "
            f"(x{n(mult.get(foco), '{:.1f}')}); el resto de barras esta atenuado."
        )
    if regimen_filtro != "Ambos":
        puntos.append(
            f"Con el filtro en <b>{regimen_filtro}</b> solo se dibuja esa serie de barras. "
            f"Ponlo en 'Ambos' para poder comparar las dos alturas lado a lado."
        )

    tabla = pd.DataFrame({
        "Activo": [etiqueta(a) for a in activos_sel],
        "Vol. calma": [f"{v:.1f}%" if pd.notna(v) else "—" for v in v_calma],
        "Vol. crisis": [f"{v:.1f}%" if pd.notna(v) else "—" for v in v_crisis],
        "Multiplo": [f"x{v:.1f}" if pd.notna(v) else "—" for v in mult],
    })

    return _cierre(Bloque(
        titulo="Volatilidad por regimen",
        eyebrow="Como leer esta pantalla",
        lead=lead, puntos=puntos, tabla=tabla,
        tabla_titulo="Volatilidad anualizada media por regimen",
    ))


# ---------------------------------------------------------------------------
# Vista 3 - Correlacion
# ---------------------------------------------------------------------------
def _pares(corr, activos_sel):
    """Serie con todos los pares (i<j) de una matriz de correlacion."""
    out = {}
    for i in range(len(activos_sel)):
        for j in range(i + 1, len(activos_sel)):
            a, b = activos_sel[i], activos_sel[j]
            try:
                r = corr.loc[a, b]
            except KeyError:
                continue
            if pd.notna(r):
                out[(a, b)] = float(r)
    return pd.Series(out, dtype=float)


def correlacion(retornos, regimen_din, regimen_filtro, activos_sel, min_obs_corr,
                foco) -> Bloque:
    reg = regimen_din.reindex(retornos.index)
    corr_calma = retornos[reg == "Calma"].corr(min_periods=min_obs_corr)
    corr_crisis = retornos[reg == "Crisis"].corr(min_periods=min_obs_corr)
    n_calma, n_crisis = int((reg == "Calma").sum()), int((reg == "Crisis").sum())

    p_calma = _pares(corr_calma, activos_sel)
    p_crisis = _pares(corr_crisis, activos_sel)
    comunes = p_calma.index.intersection(p_crisis.index)
    delta = (p_crisis[comunes] - p_calma[comunes]).sort_values(ascending=False) \
        if len(comunes) else pd.Series(dtype=float)

    n_pares = len(activos_sel) * (len(activos_sel) - 1) // 2
    lead = (
        f"Cada celda es la correlacion de un par de ETFs: cerca de <b>+1</b> (tono "
        f"calido) se mueven juntos, cerca de <b>-1</b> (tono frio) se cubren entre si, "
        f"cerca de <b>0</b> (neutro) son independientes. El panel izquierdo es calma y "
        f"el derecho crisis, con la misma escala, para que la comparacion sea "
        f"legitima. Con tus {n(len(activos_sel), '{:.0f}')} activos hay "
        f"{n(n_pares, '{:.0f}')} pares distintos, calculados sobre "
        f"{n(n_calma, '{:,.0f}')} dias de calma y {n(n_crisis, '{:,.0f}')} de crisis."
    )

    puntos = []
    if len(p_calma) and len(p_crisis):
        puntos.append(
            f"La correlacion media entre tus activos pasa de {n(p_calma.mean())} en calma "
            f"a {n(p_crisis.mean())} en crisis. Si el segundo numero es mayor, la "
            f"diversificacion de esta cartera <b>se debilita</b> justo cuando mas la "
            f"necesitas: es la tesis central del tablero, medida sobre TU seleccion."
        )
        alto_c = (p_calma.abs() > 0.5).sum()
        alto_x = (p_crisis.abs() > 0.5).sum()
        puntos.append(
            f"Pares con |correlacion| por encima de 0.5: {n(alto_c, '{:.0f}')} en calma "
            f"frente a {n(alto_x, '{:.0f}')} en crisis, de {n(n_pares, '{:.0f}')} posibles. "
            f"Cuantos mas pares cruzan ese umbral, menos posiciones realmente "
            f"independientes tienes."
        )
    if len(delta):
        (a, b), d = delta.index[0], delta.iloc[0]
        puntos.append(
            f"El par que mas se acopla al llegar la crisis es <b>{a}–{b}</b>: sube de "
            f"{n(p_calma[(a, b)])} a {n(p_crisis[(a, b)])} ({n(d, '{:+.2f}')}). Busca esa "
            f"celda: es donde tu cobertura se evapora."
        )
        (a2, b2), d2 = delta.index[-1], delta.iloc[-1]
        puntos.append(
            f"En el otro extremo, <b>{a2}–{b2}</b> es el que mas se desacopla "
            f"({n(p_calma[(a2, b2)])} → {n(p_crisis[(a2, b2)])}, {n(d2, '{:+.2f}')}). "
            f"Un par que <b>baja</b> su correlacion en crisis es una cobertura que si "
            f"funciona cuando hace falta."
        )
        mejor_hedge = p_crisis.idxmin()
        puntos.append(
            f"El refugio mas util de tu seleccion en crisis es "
            f"<b>{mejor_hedge[0]}–{mejor_hedge[1]}</b>, con la correlacion mas baja del "
            f"panel de crisis ({n(p_crisis.min())}). Si ese numero no llega a ser "
            f"negativo, ninguno de los pares en pantalla te cubre de verdad."
        )
    if foco != SIN_FOCO and foco in activos_sel:
        con_foco = [v for (x, y), v in p_crisis.items() if foco in (x, y)]
        if con_foco:
            puntos.append(
                f"<b>{etiqueta(foco)}</b> esta en foco (fila y columna recuadradas): su "
                f"correlacion media con el resto en crisis es "
                f"{n(float(np.mean(con_foco)))}."
            )
    if n_crisis < min_obs_corr:
        puntos.append(
            f"Aviso metodologico: solo hay {n(n_crisis, '{:.0f}')} dias de crisis en este "
            f"recorte (el minimo recomendado es {n(min_obs_corr, '{:.0f}')}). Las cifras "
            f"del panel de crisis son fragiles; amplia el rango o baja el umbral."
        )

    tabla = None
    if len(delta):
        top = pd.concat([delta.head(5), delta.tail(5)]).drop_duplicates()
        tabla = pd.DataFrame({
            "Par": [f"{a}–{b}" for a, b in top.index],
            "Calma": [f"{p_calma[k]:.2f}" for k in top.index],
            "Crisis": [f"{p_crisis[k]:.2f}" for k in top.index],
            "Cambio": [f"{v:+.2f}" for v in top.values],
        })

    return _cierre(Bloque(
        titulo="Correlacion por regimen",
        eyebrow="Como leer esta pantalla",
        lead=lead, puntos=puntos, tabla=tabla,
        tabla_titulo="Pares que mas se acoplan y mas se desacoplan en crisis",
    ))


def correlacion_par(retornos, regimen_din, par_a, par_b, ventana, crisis_din) -> Bloque:
    """Lectura guiada del modulo de correlacion rolling, para el par que sea."""
    roll = retornos[par_a].rolling(ventana, min_periods=int(ventana * 0.6)).corr(retornos[par_b])
    reg = regimen_din.reindex(roll.index)
    m_calma = roll[reg == "Calma"].mean()
    m_crisis = roll[reg == "Crisis"].mean()
    valido = roll.dropna()

    lead = (
        f"Esta linea unica es la correlacion de <b>{par_a}</b> con <b>{par_b}</b> "
        f"recalculada dia a dia usando solo los ultimos {n(ventana, '{:.0f}')} dias. "
        f"El mapa de calor de arriba da un promedio por regimen; esto muestra "
        f"<b>cuando</b> ocurre el acoplamiento."
    )

    puntos = []
    if len(valido):
        dif = m_crisis - m_calma
        if pd.isna(dif):
            faltante = "calma" if pd.isna(m_calma) else "crisis"
            puntos.append(
                f"Media del par en calma: {n(m_calma)}. Media en crisis: {n(m_crisis)}. "
                f"No se puede comparar: en este recorte no hay dias de <b>{faltante}</b> "
                f"suficientes para la ventana elegida. Amplia el rango o mueve el umbral "
                f"de VIX para tener los dos regimenes."
            )
        else:
            veredicto = (
                "el par <b>se acopla</b> cuando llega el panico, justo cuando esperabas "
                "que te protegiera." if dif > 0.05 else
                "el par <b>se desacopla</b> en el panico, que es exactamente lo que hace "
                "una cobertura util." if dif < -0.05 else
                "el par apenas cambia de comportamiento entre regimenes."
            )
            puntos.append(
                f"Media del par en calma: {n(m_calma)}. Media en crisis: {n(m_crisis)}. "
                f"Diferencia: {n(dif, '{:+.2f}')} — {veredicto}"
            )
        puntos.append(
            f"El recorrido de la linea va de {n(valido.min())} (minimo, "
            f"{valido.idxmin().date()}) a {n(valido.max())} (maximo, "
            f"{valido.idxmax().date()}). Cuanto mas amplio el recorrido, menos estable "
            f"es la relacion entre estos dos activos."
        )
        puntos.append(
            f"La ventana de {n(ventana, '{:.0f}')} dias es un zoom: bajala para detectar "
            f"cambios rapidos a costa de mas ruido, subela para ver la tendencia "
            f"estructural. Las bandas calidas marcan los tramos de crisis: lo importante "
            f"es si los picos y valles coinciden con ellas."
        )
    else:
        puntos.append(
            f"No hay suficientes datos solapados entre {par_a} y {par_b} para una ventana "
            f"de {n(ventana, '{:.0f}')} dias en este rango. Prueba con una ventana mas "
            f"corta o un rango mas amplio."
        )

    return _cierre(Bloque(
        titulo=f"Correlacion rolling {par_a}–{par_b}",
        eyebrow="Como leer este grafico",
        lead=lead, puntos=puntos,
    ))


# ---------------------------------------------------------------------------
# Vista 4 - Drawdown
# ---------------------------------------------------------------------------
def drawdown(dd, stats, crisis_din, activos_sel, foco) -> Bloque:
    lead = (
        f"Cada linea mide cuanto ha caido un ETF <b>desde su propio maximo previo</b>. "
        f"Cero significa que el activo esta en maximos; -20% significa que sigue un "
        f"20% por debajo del mejor momento que habia alcanzado. Se dibujan "
        f"{n(len(activos_sel), '{:.0f}')} activos ({_listado(activos_sel)}) y las bandas "
        f"calidas marcan los episodios de crisis."
    )

    puntos = []
    if not stats.empty:
        peor = stats.iloc[0]
        puntos.append(
            f"La caida mas profunda del set es la de <b>{peor['Activo']}</b>: "
            f"{n(peor['Peor drawdown'], '{:.1f}')}% con valle el {peor['Fecha valle']}. "
            f"Recuperarse de una caida asi exige una subida mayor que la caida: "
            f"perder 50% obliga a ganar 100% para volver al punto de partida."
        )
        sin_rec = stats[stats["Recuperacion"] == "sin recuperar"]
        puntos.append(
            f"{n(len(sin_rec), '{:.0f}')} de {n(len(stats), '{:.0f}')} activos "
            f"<b>todavia no han vuelto</b> a su maximo previo dentro del rango"
            + (f" ({_listado([str(x) for x in sin_rec['_codigo']])})." if len(sin_rec) else ".")
        )
        dias = [int(r.split()[0]) for r in stats["Recuperacion"] if r.endswith("d")]
        if dias:
            puntos.append(
                f"De los que si se recuperaron, tardaron entre {n(min(dias), '{:.0f}')} y "
                f"{n(max(dias), '{:.0f}')} dias desde el valle, con una mediana de "
                f"{n(float(np.median(dias)), '{:.0f}')} dias. El tiempo bajo el agua "
                f"importa tanto como la profundidad."
            )
        puntos.append(
            f"El peor drawdown promedio de los activos en pantalla es "
            f"{n(stats['Peor drawdown'].mean(), '{:.1f}')}%."
        )
    if len(dd):
        prof = (dd < -0.10).sum(axis=1)
        if prof.max() > 1:
            dia = prof.idxmax()
            puntos.append(
                f"El dia de dolor mas generalizado del rango es el <b>{dia.date()}</b>: "
                f"{n(int(prof.max()), '{:.0f}')} de {n(len(activos_sel), '{:.0f}')} activos "
                f"estaban simultaneamente mas de un 10% por debajo de su maximo. Ese "
                f"solapamiento —no la profundidad de una linea suelta— es lo que "
                f"demuestra que la diversificacion fallo."
            )
    if foco != SIN_FOCO and foco in activos_sel and not stats.empty:
        fila = stats[stats["_codigo"] == foco]
        if not fila.empty:
            f0 = fila.iloc[0]
            puntos.append(
                f"<b>{etiqueta(foco)}</b> en foco: peor caida "
                f"{n(f0['Peor drawdown'], '{:.1f}')}% ({f0['Fecha valle']}), "
                f"recuperacion {f0['Recuperacion']}."
            )

    tabla = None
    if not stats.empty:
        tabla = stats[["Activo", "Peor drawdown", "Fecha valle", "Recuperacion"]].copy()
        tabla["Peor drawdown"] = tabla["Peor drawdown"].map(lambda v: f"{v:.1f}%")

    return _cierre(Bloque(
        titulo="Drawdown (underwater)",
        eyebrow="Como leer esta pantalla",
        lead=lead, puntos=puntos, tabla=tabla,
        tabla_titulo="Peor caida, fecha del valle y recuperacion",
    ))


# ---------------------------------------------------------------------------
# Vista 5 - Distribucion
# ---------------------------------------------------------------------------
def distribucion(retornos, regimen_din, regimen_filtro, activos_sel, foco) -> Bloque:
    reg = regimen_din.reindex(retornos.index)
    filas = []
    for a in activos_sel:
        fila = {"activo": a}
        for r in ("Calma", "Crisis"):
            s = retornos[a][reg == r].dropna()
            fila[f"n_{r}"] = len(s)
            fila[f"kurt_{r}"] = s.kurtosis() if len(s) > 3 else np.nan
            fila[f"peor_{r}"] = s.min() * 100 if len(s) else np.nan
            fila[f"std_{r}"] = s.std() * 100 if len(s) > 1 else np.nan
            fila[f"ext_{r}"] = 100 * (s.abs() > 0.02).mean() if len(s) else np.nan
        filas.append(fila)
    d = pd.DataFrame(filas).set_index("activo")

    lead = (
        f"Cada violin es la <b>forma completa</b> de los retornos diarios de un ETF: la "
        f"mitad fria es calma y la calida es crisis. Donde el violin es ancho hay muchos "
        f"dias con ese retorno; las puntas largas son los dias extremos. Se comparan "
        f"{n(len(activos_sel), '{:.0f}')} activos ({_listado(activos_sel)}) mostrando "
        f"{_frase_regimen(regimen_filtro)}."
    )

    puntos = []
    ratio = (d["std_Crisis"] / d["std_Calma"]).dropna()
    if len(ratio):
        amp = ratio.idxmax()
        puntos.append(
            f"El violin que mas se ensancha al pasar a crisis es el de "
            f"<b>{etiqueta(amp)}</b>: su dispersion diaria se multiplica por "
            f"x{n(ratio.max(), '{:.1f}')}. En promedio los activos en pantalla la "
            f"multiplican por x{n(ratio.mean(), '{:.1f}')}."
        )
    if d["kurt_Crisis"].notna().any():
        k = d["kurt_Crisis"].idxmax()
        puntos.append(
            f"La cola mas gorda en crisis es la de <b>{etiqueta(k)}</b>, con curtosis en "
            f"exceso {n(d.loc[k, 'kurt_Crisis'], '{:.1f}')}. Por encima de 0 significa "
            f"que los dias extremos son <b>mas frecuentes</b> de lo que predeciria una "
            f"campana normal: los modelos de riesgo que asumen normalidad subestiman "
            f"justo el escenario que importa."
        )
    if d["peor_Crisis"].notna().any():
        pc = d["peor_Crisis"].idxmin()
        peor_calma = d.loc[pc, "peor_Calma"]
        extra = ""
        if pd.notna(peor_calma) and peor_calma != 0:
            extra = (f", frente a {n(peor_calma, '{:.1f}')}% como su peor dia en calma "
                     f"(x{n(abs(d.loc[pc, 'peor_Crisis'] / peor_calma), '{:.1f}')} peor)")
        puntos.append(
            f"El peor dia individual en crisis lo sufre <b>{etiqueta(pc)}</b> con "
            f"{n(d.loc[pc, 'peor_Crisis'], '{:.1f}')}%{extra}."
        )
    if d["ext_Crisis"].notna().any() and d["ext_Calma"].notna().any():
        puntos.append(
            f"Dias con movimiento mayor a ±2%: {n(d['ext_Calma'].mean(), '{:.1f}')}% del "
            f"tiempo en calma contra {n(d['ext_Crisis'].mean(), '{:.1f}')}% en crisis "
            f"(promedio de los activos en pantalla). Lo que en calma es una rareza, en "
            f"crisis es rutina."
        )
    if foco != SIN_FOCO and foco in d.index:
        puntos.append(
            f"<b>{etiqueta(foco)}</b> en foco: peor dia en crisis "
            f"{n(d.loc[foco, 'peor_Crisis'], '{:.1f}')}%, curtosis "
            f"{n(d.loc[foco, 'kurt_Crisis'], '{:.1f}')}."
        )

    tabla = pd.DataFrame({
        "Activo": [etiqueta(a) for a in d.index],
        "Curtosis calma": [f"{v:.1f}" if pd.notna(v) else "—" for v in d["kurt_Calma"]],
        "Curtosis crisis": [f"{v:.1f}" if pd.notna(v) else "—" for v in d["kurt_Crisis"]],
        "Peor dia calma": [f"{v:.1f}%" if pd.notna(v) else "—" for v in d["peor_Calma"]],
        "Peor dia crisis": [f"{v:.1f}%" if pd.notna(v) else "—" for v in d["peor_Crisis"]],
    })

    return _cierre(Bloque(
        titulo="Distribucion de retornos",
        eyebrow="Como leer esta pantalla",
        lead=lead, puntos=puntos, tabla=tabla,
        tabla_titulo="Colas: curtosis en exceso y peor dia por regimen",
    ))


# ---------------------------------------------------------------------------
# Vista 6 - Contagio
# ---------------------------------------------------------------------------
def contagio(retornos, regimen_din, activos_sel, umbral_arista, regimen_red,
             min_obs_corr, foco) -> Bloque:
    reg = regimen_din.reindex(retornos.index)
    p = {r: _pares(retornos[activos_sel][reg == r].corr(min_periods=min_obs_corr), activos_sel)
         for r in ("Calma", "Crisis")}
    n_pares = len(activos_sel) * (len(activos_sel) - 1) // 2
    aristas = {r: p[r][p[r].abs() >= umbral_arista] for r in ("Calma", "Crisis")}

    lead = (
        f"Cada circulo es un ETF y cada linea un par cuya correlacion supera el umbral "
        f"que fijaste (|ρ| ≥ {n(umbral_arista)}). Grosor = fuerza del vinculo; tono "
        f"calido = se mueven juntos, frio = se cubren. Estas viendo el regimen de "
        f"<b>{regimen_red.lower()}</b> con {n(len(activos_sel), '{:.0f}')} nodos y "
        f"{n(n_pares, '{:.0f}')} conexiones posibles."
    )

    puntos = [
        f"Con este umbral se dibujan {n(len(aristas[regimen_red]), '{:.0f}')} de "
        f"{n(n_pares, '{:.0f}')} conexiones posibles "
        f"({n(100 * len(aristas[regimen_red]) / n_pares if n_pares else np.nan, '{:.0f}')}% "
        f"de densidad de red).",
        f"Comparativa directa: <b>{n(len(aristas['Calma']), '{:.0f}')} conexiones en calma "
        f"frente a {n(len(aristas['Crisis']), '{:.0f}')} en crisis</b> con el mismo umbral. "
        f"Cambia el selector de regimen sin tocar el slider: si la red se densifica, "
        f"el mercado esta funcionando como un solo bloque.",
    ]
    nuevas = [k for k in aristas["Crisis"].index if k not in aristas["Calma"].index]
    if nuevas:
        puntos.append(
            f"{n(len(nuevas), '{:.0f}')} conexiones <b>solo aparecen en crisis</b>: "
            f"{_listado([f'{a}–{b}' for a, b in nuevas], maximo=5)}. Son pares que en "
            f"tiempos normales parecian no tener nada que ver."
        )
    else:
        puntos.append(
            "Ninguna conexion nueva aparece exclusivamente en crisis con este umbral: "
            "sube o baja el slider para encontrar el punto donde la red cambia."
        )
    aislados = [a for a in activos_sel
                if not any(a in k for k in aristas[regimen_red].index)]
    if aislados:
        puntos.append(
            f"Quedan aislados en {regimen_red.lower()}: <b>{_listado(aislados)}</b>. Un "
            f"nodo sin lineas es, con este umbral, un diversificador real."
        )
    else:
        puntos.append(
            f"En {regimen_red.lower()} <b>ningun activo queda aislado</b>: todos superan "
            f"el umbral con al menos otro. No hay refugio en esta seleccion."
        )
    if foco != SIN_FOCO and foco in activos_sel:
        grado = sum(1 for k in aristas[regimen_red].index if foco in k)
        puntos.append(
            f"<b>{etiqueta(foco)}</b> en foco tiene {n(grado, '{:.0f}')} conexiones en "
            f"{regimen_red.lower()}; el resto de la red esta atenuada."
        )

    tabla = None
    if len(aristas[regimen_red]):
        top = aristas[regimen_red].abs().sort_values(ascending=False).head(10).index
        tabla = pd.DataFrame({
            "Par": [f"{a}–{b}" for a, b in top],
            "Calma": [f"{p['Calma'].get(k, float('nan')):.2f}" for k in top],
            "Crisis": [f"{p['Crisis'].get(k, float('nan')):.2f}" for k in top],
        })

    return _cierre(Bloque(
        titulo="Red de contagio",
        eyebrow="Como leer esta pantalla",
        lead=lead, puntos=puntos, tabla=tabla,
        tabla_titulo=f"Conexiones mas fuertes en {regimen_red.lower()}",
    ))
