# Anatomía del riesgo de mercado — Calma vs Crisis

Dashboard interactivo (**Streamlit + Plotly**) que muestra, con datos 100% reales de mercado,
cómo **la diversificación falla justo cuando más se necesita**: en las crisis las correlaciones
del bloque de riesgo convergen hacia 1, la volatilidad se dispara y los drawdowns se profundizan
en casi todos los activos a la vez.

Proyecto final de la materia de Visualización de Datos (Maestría en Ciencia de Datos),
estructurado sobre el modelo anidado de Munzner (Domain → What → Why → How).

> **Datos:** 11 activos + índice VIX descargados de Yahoo Finance (`yfinance`), ventana
> 2018-01-02 → 2026-07-17. Cero datos sintéticos. El régimen (Calma / Crisis) se define por
> una regla objetiva: **VIX > 30 ⇒ crisis**.

---

## 🚀 Demo rápida (local)

```bash
# 1. Clonar y entrar
git clone <URL-del-repo>
cd <carpeta-del-repo>

# 2. (Recomendado) crear entorno virtual — Python 3.11+
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. (Opcional) generar los datos una vez, para arranque offline instantáneo
python pipeline.py

# 5. Lanzar el dashboard
streamlit run app.py
```

Si omites el paso 4, la app descargará los datos de Yahoo Finance en el **primer arranque**
(tarda unos segundos) y los cachea en memoria durante la sesión.

---

## 🧭 Qué contiene el dashboard

Navegación por pestañas superiores (`st.segmented_control`); los controles del sidebar aplican
de forma **global** a todas las vistas.

| # | Vista | Qué muestra |
|---|---|---|
| 1 | **Overview** | Precios normalizados (base 100) por activo, con sombreado de los episodios de crisis y un panel de VIX con la línea de umbral. Hero-cards: VIX actual, umbral, % de días en crisis, activos en vista. |
| 2 | **Volatilidad** | Volatilidad realizada anualizada (rolling 21d, √252) promedio por activo, Calma vs Crisis. El título calcula en vivo qué activos más multiplican su volatilidad. |
| 3 | **Correlación** (MVP) | Dos heatmaps lado a lado (Calma vs Crisis), colormap divergente RdBu centrado en 0. Debajo: **correlación rolling** del par que elijas, con medias por régimen. |
| 4 | **Drawdown** | Underwater plot multi-activo (caída desde el máximo previo) + ranking de peor drawdown, fecha del valle y días de recuperación por activo. |
| 5 | **Distribución** | Violines de retornos diarios por régimen y activo (colas gordas / riesgo de cola) + tabla de curtosis en exceso y peor día por régimen. |
| 6 | **Contagio** *(opcional)* | Grafo de correlaciones sobre un umbral ajustable, por régimen: al pasar de Calma a Crisis aparecen más aristas y más gruesas — el mercado se vuelve un solo bloque. |

### Interacciones

- **Filtro de régimen** (Ambos / Calma / Crisis) global.
- **Selección de activos** (multiselect) global.
- **Selector de episodio** como *brush* rápido: Todo el periodo · COVID-19 (2020) · Alza de tasas (2022) · Personalizado (slider de fechas).
- **Umbral de crisis VIX** editable (recalcula el régimen en vivo).
- **Resaltado enlazado (vistas coordinadas / CMV):** elige un activo en "Resaltar activo" y se resalta de forma coherente en las 6 vistas (vía `st.session_state`).
- **Correlación rolling de un par** con ventana ajustable (21–252 d).
- Tooltips enriquecidos y hover unificado en las series temporales.

---

## 🗂️ Estructura del repositorio

```
├── app.py                  # Dashboard Streamlit (6 vistas + interacciones). Entrypoint.
├── styles.py               # Sistema de diseño: paleta, CSS de cards/nav/badges, helpers.
├── pipeline.py             # Pipeline de datos: build_dataset() / cargar_datos().
├── poc_riesgo_mercado.py   # PoC original (congelado, referencia histórica).
├── requirements.txt        # Dependencias con versión fijada.
├── .streamlit/config.toml  # Theme oficial (colores, tipografía, radios).
├── salidas/                # Datos generados (regenerados en la nube; ver Deploy). *gitignored*
├── autoevaluacion.md       # Cifras clave verificadas + auto-evaluación vs rúbrica.
├── wireframe_dashboard.png # Wireframe de baja fidelidad.
└── Pitch_Riesgo_Mercado.pptx  # Deck del pitch (12 slides).
```

### Arquitectura de datos

`pipeline.py` es la única fuente de datos. `app.py` **no** re-descarga ni recalcula desde cero:

- `build_dataset()` — descarga de Yahoo Finance, limpia, alinea el calendario 24/7 de BTC-USD al
  calendario bursátil, calcula features (retornos log, volatilidad rolling, drawdown, régimen) y
  guarda a `salidas/`.
- `cargar_datos()` — carga rápida desde `salidas/` (sin red).
- `app.py` intenta `cargar_datos()`; si el parquet no existe (deploy limpio), llama a
  `build_dataset()`. Todo cacheado con `st.cache_data` (una sola vez por arranque).

---

## ☁️ Deploy en Streamlit Community Cloud

1. Sube el repositorio a GitHub (`app.py` en la raíz).
2. En [share.streamlit.io](https://share.streamlit.io) → **New app**, apunta a tu repo y a `app.py`.
3. En **Advanced settings**, elige **Python 3.12 o 3.13** (pandas 3.0.2 / numpy 2.4.4 requieren 3.11+).
4. Deploy. En el primer arranque la app descarga los datos de Yahoo Finance automáticamente.

> **Pin de versión (importante).** La app usa `st.segmented_control`,
> `st.container(key=..., horizontal=..., vertical_alignment=...)` y el theme extendido de
> `.streamlit/config.toml` (`theme.font` con URL, `baseRadius`, `buttonRadius`). Estas APIs no
> existen en Streamlit < 1.5x. `requirements.txt` pinnea `streamlit==1.56.0`; no lo bajes.

> **Arranque offline / más robusto (opcional).** Yahoo Finance no es una API oficial y puede
> fallar o limitar peticiones en la nube. Si prefieres que la app no dependa de la red al
> arrancar, comenta la línea `salidas/` en `.gitignore`, corre `python pipeline.py` una vez y
> commitea `salidas/market_data.parquet` y `salidas/drawdown.parquet`. La app los usará
> directamente sin descargar nada.

### Refrescar los datos

```bash
python pipeline.py    # vuelve a descargar y regenera todo en ./salidas/
```

---

## ⚠️ Limitaciones de los datos (honestidad metodológica)

- **Fuente no oficial.** `yfinance` scrapea Yahoo Finance; no es una API institucional. Yahoo
  puede **revisar precios ajustados históricos** entre descargas — por eso el multiplicador de
  volatilidad en crisis puede variar levemente entre fechas de descarga (documentado en
  `autoevaluacion.md`). La tesis central (convergencia de correlaciones en crisis) es estable.
- **Precios ajustados (`auto_adjust`).** Se usa el cierre ajustado por dividendos/splits.
- **Alineación de calendarios.** BTC-USD cotiza 24/7; se alinea al calendario bursátil (ETFs + VIX).
  Los activos con historia más corta conservan su ventana real (cálculos NaN-aware, sin `dropna()` global).
- **Historia corta de BTC-USD** frente al resto; sus estadísticas por régimen tienen menos observaciones.
- **Umbral VIX > 30** es una regla simple y reproducible, no una clasificación oficial de crisis.

---

## 📊 Hallazgo principal (con las cifras reales)

- Correlación media del bloque de riesgo (SPY·QQQ·HYG): **0.78 (calma) → 0.85 (crisis)**.
- SPY–TLT: **−0.05 → −0.32** — el refugio real (bonos largos) se desacopla *más* en crisis
  (matiz honesto de la tesis: la convergencia a 1 es real *dentro* del bloque de riesgo).
- Volatilidad anualizada calma→crisis: SPY ×2.6, HYG ×3.2, VNQ ×2.6.
- Peor drawdown: BTC-USD −81.4%, TLT −48.4%, VNQ −42.4%, DBC −41.7%, EEM −39.8%.

---

## 🛠️ Stack

Python 3.11+ · Streamlit 1.56 · Plotly 6.7 · pandas 3.0 · numpy 2.4 · yfinance 1.5 · pyarrow 23.

## 📄 Licencia / uso

Proyecto académico con fines educativos. **No es asesoría de inversión.**
