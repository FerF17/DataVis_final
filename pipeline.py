"""
pipeline.py
Fase A - Ingesta y features: pipeline de datos reutilizable del dashboard de riesgo de mercado.

Extiende poc_riesgo_mercado.py (universo ampliado a 11 activos, manejo del calendario 24/7 de
BTC-USD, auditoria de calidad de datos) y lo empaqueta en funciones importables para que
app.py (Streamlit) cargue el dataset ya calculado en vez de recalcularlo en cada carga.

Uso como script (descarga y actualiza los datos en ./salidas):
    python pipeline.py

Uso como modulo (dashboard, notebooks de verificacion, etc.):
    from pipeline import build_dataset, cargar_datos

    # Recalcular todo desde Yahoo Finance y guardar a disco:
    data = build_dataset()

    # Carga rapida desde los archivos ya guardados (sin red, sin recalculo pesado):
    data = cargar_datos()

    precios, retornos, vol, drawdown = data["precios"], data["retornos"], data["vol_realizada"], data["drawdown"]
"""

import os
import shutil

import numpy as np
import pandas as pd
import yfinance as yf

# --- Configuracion -------------------------------------------------------------
ACTIVOS = ["SPY", "QQQ", "TLT", "GLD", "HYG", "VNQ", "EEM", "DBC", "UUP", "BTC-USD"]
# acciones, tech, bonos, oro, credito HY, real estate, emergentes, commodities, dolar, cripto
ACTIVOS_24_7 = {"BTC-USD"}  # cotizan todos los dias del calendario (incl. fines de semana/feriados)
VIX = "^VIX"                # termometro de regimen
INICIO = "2018-01-01"       # cubre COVID-2020 y alza de tasas 2022
UMBRAL_CRISIS = 30          # VIX > 30 => crisis (regla objetiva, ya validada)
VENTANA_VOL = 21            # ~1 mes bursatil
MIN_OBS_CORR = 30           # minimo de observaciones superpuestas para confiar en una correlacion
OUT = "salidas"

# --- Decision de diseno: calendario 24/7 de BTC-USD (Fase A, paso 2 del README) -
# BTC-USD cotiza todos los dias (incl. fines de semana/feriados bursatiles), mientras que los
# ETFs y el VIX solo cotizan en dias habiles de mercado. Se evaluaron dos opciones:
#   (a) recortar TODO el dataset al inicio comun mas reciente entre los 11 activos, o
#   (b) mantener el calendario bursatil (ETFs + VIX) como indice maestro y alinear cada activo
#       a ese calendario, dejando NaN explicito antes de su propio inicio de cotizacion.
# Se elige (b): recortar (a) perderia cobertura de COVID-2020 y del ciclo de tasas 2022 para
# el resto de activos solo por acomodar una serie mas nueva/distinta. Con (b) cada activo
# conserva su ventana real; los calculos rio abajo (retornos, vol rolling, correlaciones) usan
# NaN-aware operations de pandas (rolling min_periods, corr pairwise) en vez de un dropna()
# global, por lo que las ventanas heterogeneas no contaminan las series de activos mas antiguos.
# Si en el futuro se agrega un activo que empiece a cotizar despues de INICIO, su ventana previa
# quedara igualmente en NaN sin forzar un recorte global.


def _limpiar_cache_yfinance():
    cache_dir = os.path.expanduser("~/.cache/yfinance")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
        except OSError:
            pass


def descargar_precios(activos=ACTIVOS, vix=VIX, inicio=INICIO):
    """Descarga precios (Close, auto-adjusted) de Yahoo Finance. 100% datos reales."""
    _limpiar_cache_yfinance()
    print("Descargando datos reales de Yahoo Finance...")
    raw = yf.download(activos + [vix], start=inicio, auto_adjust=True, progress=False)["Close"]
    return raw


def _alinear_al_calendario_bursatil(raw, activos=ACTIVOS, vix=VIX, activos_24_7=ACTIVOS_24_7):
    """Alinea todos los activos al calendario bursatil (dado por los activos que NO cotizan
    24/7, mas el VIX) y registra huecos rellenados por activo para auditoria de calidad."""
    activos_calendario = [a for a in activos if a not in activos_24_7]
    calendario = raw[activos_calendario + [vix]].dropna(how="all").index
    alineado = raw.reindex(calendario)

    limpio = pd.DataFrame(index=calendario)
    filas_log = []
    for col in activos + [vix]:
        serie = alineado[col]
        primer_valido = serie.first_valid_index()
        if primer_valido is None:
            limpio[col] = serie
            filas_log.append({"activo": col, "primer_dato": None, "huecos_rellenados": 0,
                               "dias_disponibles": 0})
            continue
        huecos_rellenados = int(serie.loc[primer_valido:].isna().sum())
        limpio[col] = serie.ffill()
        filas_log.append({
            "activo": col,
            "primer_dato": primer_valido.date(),
            "huecos_rellenados": huecos_rellenados,
            "dias_disponibles": int(limpio[col].loc[primer_valido:].notna().sum()),
        })

    log_calidad = pd.DataFrame(filas_log)
    return limpio, log_calidad


def calcular_features(limpio, activos=ACTIVOS, vix=VIX, umbral_crisis=UMBRAL_CRISIS,
                       ventana_vol=VENTANA_VOL):
    """Calcula retornos log, volatilidad rolling anualizada, drawdown y regimen (Calma/Crisis).

    No se usa dropna() global: cada activo conserva su propia ventana (ver nota de diseno
    arriba sobre BTC-USD / activos con historia mas corta o distinta).
    """
    precios = limpio[activos]
    vix_al = limpio[vix]

    retornos = np.log(precios / precios.shift(1))
    vol_realizada = retornos.rolling(ventana_vol, min_periods=ventana_vol).std() * np.sqrt(252)
    drawdown = precios / precios.cummax() - 1

    crisis = vix_al > umbral_crisis
    regimen = pd.Series(np.where(crisis, "Crisis", "Calma"), index=precios.index, name="regimen")

    return {
        "precios": precios,
        "vix": vix_al,
        "retornos": retornos,
        "vol_realizada": vol_realizada,
        "drawdown": drawdown,
        "crisis": crisis,
        "regimen": regimen,
    }


def calcular_correlaciones(retornos, crisis, min_periods=MIN_OBS_CORR):
    """Matrices de correlacion por regimen. pandas.corr() ya maneja NaN de forma pairwise,
    por lo que activos con ventanas distintas simplemente usan su periodo superpuesto."""
    crisis_ret = crisis.reindex(retornos.index)
    corr_calma = retornos[~crisis_ret.values].corr(min_periods=min_periods)
    corr_crisis = retornos[crisis_ret.values].corr(min_periods=min_periods)
    return corr_calma, corr_crisis


def _advertencias(features, log_calidad):
    crisis = features["crisis"]
    pct_crisis = 100 * crisis.mean()
    print(f"Dias en crisis: {pct_crisis:.1f}%  |  rango: {features['precios'].index.min().date()} "
          f"a {features['precios'].index.max().date()}")

    con_huecos = log_calidad[log_calidad["huecos_rellenados"] > 0]
    if len(con_huecos) > 0:
        print("Huecos internos rellenados por ffill (auditoria de calidad de datos):")
        for _, fila in con_huecos.iterrows():
            print(f"  - {fila['activo']}: {fila['huecos_rellenados']} dias")

    ventanas_recortadas = log_calidad[log_calidad["primer_dato"].notna() &
                                       (pd.to_datetime(log_calidad["primer_dato"]) > pd.Timestamp(INICIO))]
    if len(ventanas_recortadas) > 0:
        print("Activos con ventana propia (cotizan desde despues de INICIO, NaN antes de esa fecha):")
        for _, fila in ventanas_recortadas.iterrows():
            print(f"  - {fila['activo']}: primer dato {fila['primer_dato']}")

    if crisis.sum() == 0:
        print("Advertencia: no se detectaron dias de crisis en el periodo. Verifica la descarga del VIX.")


def build_dataset(activos=ACTIVOS, vix=VIX, inicio=INICIO, umbral_crisis=UMBRAL_CRISIS,
                   ventana_vol=VENTANA_VOL, out_dir=OUT, guardar=True):
    """Pipeline completo: descarga -> limpieza/alineacion -> features -> (opcional) guardado.

    Devuelve un dict con todos los DataFrames listos para que el dashboard los consuma.
    """
    raw = descargar_precios(activos, vix, inicio)
    limpio, log_calidad = _alinear_al_calendario_bursatil(raw, activos, vix)
    features = calcular_features(limpio, activos, vix, umbral_crisis, ventana_vol)
    corr_calma, corr_crisis = calcular_correlaciones(features["retornos"], features["crisis"])

    _advertencias(features, log_calidad)

    market_data = features["precios"].copy()
    market_data["VIX"] = features["vix"]
    market_data["regimen"] = features["regimen"].values

    data = {
        "precios": features["precios"],
        "vix": features["vix"],
        "retornos": features["retornos"],
        "vol_realizada": features["vol_realizada"],
        "drawdown": features["drawdown"],
        "regimen": features["regimen"],
        "corr_calma": corr_calma,
        "corr_crisis": corr_crisis,
        "log_calidad": log_calidad,
        "market_data": market_data,
        "umbral_crisis": umbral_crisis,
        "ventana_vol": ventana_vol,
    }

    if guardar:
        guardar_salidas(data, out_dir)

    return data


def guardar_salidas(data, out_dir=OUT):
    os.makedirs(out_dir, exist_ok=True)
    data["market_data"].to_parquet(f"{out_dir}/market_data.parquet")
    data["drawdown"].to_parquet(f"{out_dir}/drawdown.parquet")
    data["corr_calma"].to_csv(f"{out_dir}/corr_calma.csv")
    data["corr_crisis"].to_csv(f"{out_dir}/corr_crisis.csv")
    data["log_calidad"].to_csv(f"{out_dir}/data_quality_log.csv", index=False)
    print(f"Guardado en ./{out_dir}/: market_data.parquet, drawdown.parquet, "
          f"corr_calma.csv, corr_crisis.csv, data_quality_log.csv")


def cargar_datos(out_dir=OUT, activos=ACTIVOS, umbral_crisis=UMBRAL_CRISIS, ventana_vol=VENTANA_VOL):
    """Carga rapida desde los archivos ya guardados (sin red, sin re-descarga).

    Pensado para que app.py importe esto en vez de llamar a build_dataset() en cada carga.
    Recalcula retornos/vol/drawdown en memoria (barato: son ~operaciones vectorizadas sobre
    un DataFrame ya limpio) para no tener que mantener sincronizados varios parquet derivados.
    """
    market_data = pd.read_parquet(f"{out_dir}/market_data.parquet")
    precios = market_data[activos]
    vix_al = market_data["VIX"]
    regimen = market_data["regimen"]
    crisis = regimen == "Crisis"

    retornos = np.log(precios / precios.shift(1))
    vol_realizada = retornos.rolling(ventana_vol, min_periods=ventana_vol).std() * np.sqrt(252)
    drawdown = pd.read_parquet(f"{out_dir}/drawdown.parquet")

    corr_calma = pd.read_csv(f"{out_dir}/corr_calma.csv", index_col=0)
    corr_crisis = pd.read_csv(f"{out_dir}/corr_crisis.csv", index_col=0)
    log_calidad = pd.read_csv(f"{out_dir}/data_quality_log.csv")

    return {
        "precios": precios,
        "vix": vix_al,
        "retornos": retornos,
        "vol_realizada": vol_realizada,
        "drawdown": drawdown,
        "regimen": regimen,
        "corr_calma": corr_calma,
        "corr_crisis": corr_crisis,
        "log_calidad": log_calidad,
        "market_data": market_data,
        "umbral_crisis": umbral_crisis,
        "ventana_vol": ventana_vol,
    }


def verificar_cifras_clave(data):
    """Imprime las cifras clave para comparar rapidamente contra autoevaluacion.md
    (Fase A, paso 5 del README: no recalcular ciegamente, confirmar consistencia)."""
    precios, retornos, vol, dd = data["precios"], data["retornos"], data["vol_realizada"], data["drawdown"]
    regimen = data["regimen"]

    print("\n--- Verificacion de cifras clave ---")
    print(f"Ventana: {precios.index.min().date()} -> {precios.index.max().date()} "
          f"({len(precios)} dias bursatiles)")

    pct_crisis = 100 * (regimen == "Crisis").mean()
    vix_calma = data["vix"][regimen == "Calma"].mean()
    vix_crisis = data["vix"][regimen == "Crisis"].mean()
    print(f"Dias en crisis (VIX > {data['umbral_crisis']}): {pct_crisis:.1f}%  |  "
          f"VIX medio calma/crisis: {vix_calma:.1f} / {vix_crisis:.1f}  |  pico VIX: {data['vix'].max():.1f}")

    print("Volatilidad anualizada calma -> crisis (x veces):")
    for activo in precios.columns:
        v_calma = vol[activo][regimen == "Calma"].mean()
        v_crisis = vol[activo][regimen == "Crisis"].mean()
        if pd.notna(v_calma) and pd.notna(v_crisis):
            print(f"  {activo}: {100*v_calma:.1f}% -> {100*v_crisis:.1f}% (x{v_crisis/v_calma:.1f})")

    bloque_riesgo = [a for a in ["SPY", "QQQ", "HYG"] if a in retornos.columns]
    if len(bloque_riesgo) >= 2:
        crisis_ret = (regimen == "Crisis").reindex(retornos.index)
        corr_calma_bloque = retornos.loc[~crisis_ret.values, bloque_riesgo].corr().values
        corr_crisis_bloque = retornos.loc[crisis_ret.values, bloque_riesgo].corr().values
        n = len(bloque_riesgo)
        media_calma = (corr_calma_bloque.sum() - n) / (n * n - n)
        media_crisis = (corr_crisis_bloque.sum() - n) / (n * n - n)
        print(f"Correlacion media bloque de riesgo ({'/'.join(bloque_riesgo)}): "
              f"{media_calma:.2f} (calma) -> {media_crisis:.2f} (crisis)")

    print("Peor drawdown por activo:")
    for activo in dd.columns:
        peor = dd[activo].min()
        if pd.notna(peor):
            print(f"  {activo}: {100*peor:.1f}%")
    print("--- Fin verificacion ---\n")


if __name__ == "__main__":
    dataset = build_dataset()
    verificar_cifras_clave(dataset)
