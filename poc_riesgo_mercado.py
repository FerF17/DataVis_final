"""
PoC preliminar — Anatomia del riesgo de mercado (calma vs crisis)
Descarga ETFs REALES de Yahoo Finance, calcula features y genera 3 figuras + parquet.
Sin datos sinteticos.

Uso:
    pip install yfinance pandas numpy matplotlib pyarrow
    python poc_riesgo_mercado.py

Salidas (carpeta ./salidas):
    market_data.parquet     precios ajustados + VIX + regimen
    corr_calma.csv / corr_crisis.csv
    fig1_correlaciones.png  dos heatmaps lado a lado (climax narrativo)
    fig2_volatilidad.png    vol realizada media por activo y regimen
    fig3_drawdown_spy.png   underwater plot de SPY con crisis sombreadas
"""

import os
import shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

# --- Configuracion -----------------------------------------------------------
ACTIVOS = ["SPY", "QQQ", "TLT", "GLD", "HYG"]   # acciones, tech, bonos, oro, credito HY
VIX = "^VIX"                                      # termometro de regimen
INICIO = "2018-01-01"                             # cubre COVID-2020 y alza de tasas 2022
UMBRAL_CRISIS = 30                                # VIX > 30 => crisis (regla objetiva)
VENTANA_VOL = 21                                  # ~1 mes bursatil
OUT = "salidas"
os.makedirs(OUT, exist_ok=True)

# --- 1. Descarga de datos reales --------------------------------------------
print("Descargando datos reales de Yahoo Finance...")
# Limpiar caché para evitar bloqueos de base de datos
cache_dir = os.path.expanduser("~/.cache/yfinance")
if os.path.exists(cache_dir):
    try:
        shutil.rmtree(cache_dir)
        print("  → Caché de yfinance limpiado")
    except:
        pass

raw = yf.download(ACTIVOS + [VIX], start=INICIO, auto_adjust=True, progress=False)["Close"]
raw = raw.dropna(how="all").ffill().dropna()

precios = raw[ACTIVOS]
vix = raw[VIX]

# --- 2. Features -------------------------------------------------------------
retornos = np.log(precios / precios.shift(1)).dropna()
vol_realizada = retornos.rolling(VENTANA_VOL).std() * np.sqrt(252)

# Regimen objetivo por umbral de VIX (alineado a precios, no retornos)
vix_al = vix.reindex(precios.index).ffill()
crisis = vix_al > UMBRAL_CRISIS
regimen = pd.Series(np.where(crisis, "Crisis", "Calma"), index=precios.index, name="regimen")

pct_crisis = 100 * crisis.mean()
print(f"Dias en crisis: {pct_crisis:.1f}%  |  rango: {precios.index.min().date()} a {precios.index.max().date()}")

# Validar que tenemos datos suficientes
if crisis.sum() == 0:
    print("⚠ Advertencia: No se detectaron días de crisis en el período. Verifica la descarga del VIX.")
if retornos.isna().sum().sum() > 0:
    print(f"⚠ Advertencia: {retornos.isna().sum().sum()} NaN en retornos.")
if vix_al.isna().sum() > 0:
    print(f"⚠ Advertencia: {vix_al.isna().sum()} NaN en VIX.")

# --- 3. Matrices de correlacion por regimen ---------------------------------
crisis_retornos = crisis.loc[retornos.index]  # alinear crisis a índice de retornos
corr_calma = retornos[~crisis_retornos.values].corr()
corr_crisis = retornos[crisis_retornos.values].corr()
corr_calma.to_csv(f"{OUT}/corr_calma.csv")
corr_crisis.to_csv(f"{OUT}/corr_crisis.csv")

# --- 4. Guardar dataset ------------------------------------------------------
export = precios.copy()
export["VIX"] = vix_al
export["regimen"] = regimen.values
export.to_parquet(f"{OUT}/market_data.parquet")

# --- Helper heatmap ----------------------------------------------------------
def heatmap(ax, M, titulo):
    im = ax.imshow(M.values, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(M))); ax.set_xticklabels(M.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(M))); ax.set_yticklabels(M.index)
    for i in range(len(M)):
        for j in range(len(M)):
            ax.text(j, i, f"{M.values[i, j]:.2f}", ha="center", va="center",
                    color="black", fontsize=9)
    ax.set_title(titulo, fontweight="bold")
    return im

# --- Fig 1: correlaciones calma vs crisis (climax) --------------------------
if len(corr_calma) > 0 and len(corr_crisis) > 0:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    heatmap(axes[0], corr_calma, f"Calma (VIX <= {UMBRAL_CRISIS})")
    im = heatmap(axes[1], corr_crisis, f"Crisis (VIX > {UMBRAL_CRISIS})")
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.04, label="Correlacion")
    fig.suptitle("La diversificacion falla en las crisis: las correlaciones convergen",
                 fontsize=13, fontweight="bold")
    fig.savefig(f"{OUT}/fig1_correlaciones.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
else:
    print("⚠ No se pudo generar Fig 1: datos insuficientes")

# --- Fig 2: volatilidad media por activo y regimen --------------------------
vol_por_regimen = vol_realizada.groupby(regimen.loc[vol_realizada.index]).mean().T  # activos x regimen
cols = [c for c in ["Calma", "Crisis"] if c in vol_por_regimen.columns]
if len(cols) > 0 and not vol_por_regimen[cols].isna().all().all():
    fig, ax = plt.subplots(figsize=(9, 5))
    vol_por_regimen[cols].plot(kind="bar", ax=ax, color=["#4C78A8", "#E45756"][:len(cols)])
    ax.set_ylabel("Volatilidad realizada anualizada")
    ax.set_title("La volatilidad se dispara en crisis (todos los activos)", fontweight="bold")
    ax.set_xlabel(""); ax.legend(title="Regimen")
    fig.savefig(f"{OUT}/fig2_volatilidad.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
else:
    print("⚠ No se pudo generar Fig 2: datos insuficientes")

# --- Fig 3: drawdown (underwater) de SPY ------------------------------------
if "SPY" in precios.columns and not precios["SPY"].isna().all():
    spy = precios["SPY"]
    dd = spy / spy.cummax() - 1
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.fill_between(dd.index, dd.values, 0, color="#E45756", alpha=0.5)
    ax.plot(dd.index, dd.values, color="#B22222", linewidth=0.8)
    ymin = ax.get_ylim()[0]
    crisis_retornos = crisis.loc[retornos.index]  # alinear crisis a índice de retornos
    ax.fill_between(retornos.index, ymin, 0, where=crisis_retornos.values,
                    color="gray", alpha=0.18, label="Crisis (VIX>30)")
    ax.set_ylabel("Drawdown"); ax.set_title("Drawdown de SPY y episodios de crisis",
                                             fontweight="bold")
    ax.legend(loc="lower right")
    fig.savefig(f"{OUT}/fig3_drawdown_spy.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
else:
    print("⚠ No se pudo generar Fig 3: SPY no disponible")

print(f"Listo. Revisa la carpeta ./{OUT}/")
