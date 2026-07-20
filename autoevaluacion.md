# Auto-evaluación del pitch — "Anatomía del riesgo de mercado"

## Cifras clave verificadas — PoC original, 5 activos (leídas de `market_data.parquet`, snapshot al 2026-07-09)

| Métrica | Valor real |
|---|---|
| Ventana | 2018-01-02 → 2026-07-09 (2 141 días bursátiles) |
| Días en crisis (VIX > 30) | 154 = **7.2 %** |
| VIX medio: calma / crisis | 18.3 / 38.0 |
| VIX máximo | 82.69 (16-mar-2020) |
| Volatilidad anual. calma→crisis | SPY 14.6→48.2 (×3.3) · QQQ 20.0→51.8 (×2.6) · HYG 6.2→23.2 (×3.8) · TLT 13.9→29.0 (×2.1) · GLD 16.3→23.2 (×1.4) |
| Correlación bloque de riesgo (SPY·QQQ·HYG) | 0.78 (calma) → **0.85 (crisis)** |
| SPY–QQQ / SPY–HYG | 0.93→0.97 / 0.74→0.82 |
| SPY–TLT (refugio real) | −0.05 → **−0.32** (se desacopla más en crisis) |
| Peor drawdown | SPY −33.7 % (mar-2020) · QQQ −35.1 % (2022) · TLT −48.4 % (2023) · GLD −26.2 % · HYG −22.0 % |

> **Matiz honesto sobre la tesis:** la convergencia hacia 1 es real **dentro del bloque de riesgo**; los bonos largos (TLT) son el refugio genuino y se desacoplan aún más. El deck presenta este hallazgo tal cual lo muestran los datos.

## Fase A — Estado de avance (completada 2026-07-19)

`pipeline.py` reemplaza a `poc_riesgo_mercado.py` como fuente de datos: universo ampliado a 11 activos (agrega VNQ, EEM, DBC, UUP, BTC-USD), alineación de calendario bursátil para BTC-USD (24/7), log de calidad de datos por activo, drawdown para los 11 activos, y funciones `build_dataset()` / `cargar_datos()` importables por el dashboard. Detalle completo de las decisiones en el README §1.4 y en el comentario de diseño al inicio de `pipeline.py`.

### Cifras clave — universo ampliado, 11 activos (`salidas/market_data.parquet`, snapshot al 2026-07-19)

| Métrica | Valor real | vs. PoC original (5 activos) |
|---|---|---|
| Ventana | 2018-01-02 → 2026-07-17 (2 147 días bursátiles) | +6 días bursátiles (rango casi idéntico) |
| Días en crisis (VIX > 30) | **7.2 %** | Sin cambios |
| VIX medio: calma / crisis | 18.3 / 38.0 | Sin cambios |
| VIX máximo | 82.7 (16-mar-2020) | Sin cambios |
| Correlación bloque de riesgo (SPY·QQQ·HYG) | 0.78 (calma) → **0.85 (crisis)** | Sin cambios |
| SPY–QQQ / SPY–HYG / SPY–TLT | 0.93→0.97 / 0.74→0.82 / −0.05→−0.32 | Sin cambios |
| Volatilidad anual. calma→crisis (5 activos originales) | SPY 14.6→**37.7** (×2.6) · QQQ 19.8→**41.4** (×2.1) · TLT 13.5→23.7 (×1.8) · GLD 14.9→20.2 (×1.4) · HYG 5.7→18.0 (×3.2) | **Crisis más baja que lo documentado** (ver nota de auditoría abajo) |
| Volatilidad anual. calma→crisis (activos nuevos) | VNQ 16.7→43.3 (×2.6) · EEM 18.2→35.8 (×2.0) · DBC 16.5→26.0 (×1.6) · UUP 6.2→10.1 (×1.6) · BTC-USD 56.7→79.4 (×1.4) | Sin precedente (activos nuevos) |
| Peor drawdown | SPY −33.7 % · QQQ −35.1 % · TLT −48.4 % · GLD −26.4 % · HYG −22.0 % · VNQ −42.4 % · EEM −39.8 % · DBC −41.7 % · UUP −14.2 % · BTC-USD −81.4 % | Prácticamente sin cambios (GLD −26.2→−26.4, resto igual) |

### ⚠️ Nota de auditoría: discrepancia en volatilidad realizada durante crisis

Al reverificar cifras (README Fase A, paso 5) se encontró que la volatilidad anualizada en crisis salió más baja que la documentada originalmente (p. ej. SPY 48.2% → 37.7%, QQQ 51.8% → 41.4%, HYG 23.2% → 18.0%), mientras que el % de días en crisis, el VIX medio y **todas** las correlaciones por régimen (incluidas SPY–QQQ, SPY–HYG, SPY–TLT) se mantuvieron idénticas.

**Se descartó que fuera un bug del pipeline nuevo**: se reprodujo el cálculo con el código *exacto* de `poc_riesgo_mercado.py` (mismos 5 activos, sin ninguno de los cambios de `pipeline.py`) sobre una descarga fresca de Yahoo Finance, y el resultado fue el mismo 37.7% para SPY. Como la clasificación de régimen (qué días son "Crisis") no cambió, la causa más probable es que Yahoo Finance revisó los precios ajustados históricos (`auto_adjust`) entre la descarga original (usada para `autoevaluacion.md`/el pitch) y esta (2026-07-19) — algo conocido de la fuente y ya listado como limitación del dataset (yfinance no oficial).

**Implicación para la tesis:** no cambia. La convergencia de correlaciones en crisis (el hallazgo central del pitch) se mantiene exactamente igual; solo cambió la magnitud del multiplicador de volatilidad. Si se cita la cifra "×3.3" en el deck o el informe final, actualizar a **×2.6** (SPY) o preferir hablar de "la volatilidad se duplica o más" en vez de un múltiplo puntual, dado que es sensible a revisiones de datos de la fuente.

### Log de calidad de datos (nuevo, `salidas/data_quality_log.csv`)

Único hallazgo relevante: **2026-05-25** (feriado bursátil, mercado de EE.UU. cerrado) — Yahoo Finance reporta un valor de `^VIX` (16.59) ese día pero los 9 ETFs en NaN. El pipeline lo detecta, lo rellena por `ffill` (arrastra el cierre previo) y lo deja registrado. No afecta ninguna cifra reportada arriba (es un solo día, fuera de los episodios de crisis).

## Fase B — Estado de avance (completada 2026-07-19)

`app.py` (nuevo) implementa el esqueleto Streamlit y las Vistas 1-3 sobre `cargar_datos()` de `pipeline.py`, sin recalcular nada por su cuenta salvo agregaciones baratas (medias de volatilidad por régimen, correlaciones por régimen) que se recomputan en vivo según los controles del sidebar. Detalle completo de alcance en el README §2 "Fase B".

### Decisiones tomadas durante Fase B (no estaban en el plan original)

- **Rediseño visual tipo cards.** A pedido explícito, se migró del wireframe original (todo apilado en una sola página) a un sistema de cards con fondo en gradiente, una card oscura destacada por vista, badges y hero-metrics, inspirado en un dashboard de referencia (Crextio) pero con contenido 100% propio. Vive en `styles.py` (nuevo) + `.streamlit/config.toml` (nuevo, theme oficial de Streamlit). Solo la Vista 1 (Overview) tiene el rediseño visual profundo terminado; Volatilidad y Correlación están envueltas en el nuevo sistema de cards pero su rediseño profundo queda para una ronda incremental siguiente.
- **Nav superior por pestañas en vez de scroll vertical.** `st.segmented_control` decide qué vista se renderiza; los filtros del sidebar (activos, rango, umbral VIX, régimen) siguen aplicando globalmente sin importar la pestaña activa.
- **Recalculo dinámico de régimen/correlaciones/volatilidad.** El umbral VIX editable del sidebar recalcula `regimen` en vivo (no depende del corte fijo de 30 usado en `corr_calma.csv`/`corr_crisis.csv`); si se cambia el umbral o el rango de fechas, las cifras mostradas en el dashboard pueden diferir levemente de las de §1.3/§"Fase A" de este documento — eso es esperado y correcto, no un bug.
- **Riesgo de versión de Streamlit ya detectado.** El desarrollo ocurrió en dos entornos Python distintos con versiones de Streamlit diferentes (1.56.0 vs 1.54.0 en `msd_env`, el entorno real de trabajo). `st.segmented_control(..., required=True)` no existe en 1.54.0 y rompió la app al primer uso real — ya corregido. **Implicación para Fase C (deploy, paso 18):** pinnear `streamlit>=1.54.0` en `requirements.txt` (ver README §2, paso 18) para evitar que Streamlit Cloud instale una versión sin `st.container(key=...)`, `st.segmented_control` o el theme extendido de `config.toml`.

### Validación técnica (sin verificación visual — ver limitación abajo)

Se corrió `streamlit.testing.v1.AppTest` de forma headless sobre `app.py` para las 3 pestañas (Overview, Volatilidad, Correlación) bajo ambos entornos (1.56.0 y `msd_env` 1.54.0): las 3 cargan sin excepciones y renderizan su gráfico Plotly correspondiente.

**Limitación honesta:** no hay forma de tomar capturas de pantalla del dashboard corriendo (no hay herramienta de navegador/screenshot disponible), así que el pulido visual (alineación, contraste real, tamaños) se validó por inspección manual del usuario en `localhost:8502`, no por el asistente. Cualquier ajuste fino reportado por el usuario debe tratarse como la fuente de verdad sobre el resultado visual real, no lo que el código "debería" verse.

## Mapeo slide → entregable exigido

| # | Slide | Entregable cubierto |
|---|---|---|
| 1 | Portada | Título, tesis, alcance PoC, herramienta, fuente |
| 2 | Problema e importancia | Domain problem |
| 3 | Audiencia y contexto de uso | Audiencia + contexto (educativo, no trading) |
| 4 | Dataset | Fuente, PoC vs final, ventana, calidad/limitaciones |
| 5 | What | Tabla de atributos + tipos Munzner + derivados |
| 6 | Why | 5 preguntas analíticas mapeadas a tareas Munzner |
| 7 | How (1) | **Wireframe** del dashboard |
| 8 | How (2) | Idioms + marks/channels + **figura real correlación** |
| 9 | How (3) | Evidencia real: volatilidad + drawdown |
| 10 | Interacciones | Vistas coordinadas (CMV) |
| 11 | Factibilidad | Plan 3 semanas + riesgos y mitigaciones |
| 12 | Cierre | Síntesis + preguntas |

## Auto-calificación estimada vs rúbrica (100 pts)

| Criterio | Peso | Estimado | Notas / dónde subir |
|---|---|---|---|
| 1. Definición del dominio | 15 | **14** | Problema, importancia y audiencia claros. Subir: añadir 1 dato de mercado citado. |
| 2. What / abstracción de datos | 20 | **19** | Crudos + 5 derivados con tipos Munzner y limitaciones. Sólido. |
| 3. Why / abstracción de tareas | 20 | **18** | 5 tareas con vocabulario Munzner. Subir: mapear cada tarea a una vista concreta. |
| 4. How / propuesta (mayor peso) | 25 | **23** | Wireframe + idioms justificados con marks/channels + evidencia real. Subir: mockup de mayor fidelidad de la vista de correlación. |
| 5. Factibilidad | 10 | **10** | Plan realista + 6 riesgos mitigados, ya probados en la PoC. |
| 6. Calidad de la presentación | 10 | **9** | Diseño sobrio, un mensaje por slide, QA visual pasado. |
| **Total** | **100** | **≈ 93** | |

### Palancas para llegar a ~97
- Añadir en el slide 6 una columna "vista que la responde" (Why → How explícito).
- Incluir un mockup de alta fidelidad (captura Plotly) de la vista de correlación.
- Citar una referencia académica del fenómeno (correlaciones que convergen en crisis).
