"""
reporte.py
Self-report: genera un PDF con los datos y los insights de LAS SEIS pantallas,
sin importar en cual este parado el usuario cuando pulsa el boton.

El PDF no reinventa el analisis: consume exactamente los mismos `Bloque` de
`narrativa.py` que se pintan en pantalla, mas las tablas de respaldo. Asi el
documento descargado y el tablero nunca pueden decir cosas distintas.

Depende solo de reportlab (sin exportar imagenes de Plotly, que exigiria kaleido
y un binario de Chrome en el servidor).
"""

import io
import re
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, KeepTogether,
)

import styles as S

# --- Paleta del documento (la misma de la marca) -----------------------------
C_CREAM = colors.HexColor(S.CREAM)
C_MIST = colors.HexColor(S.MIST)
C_DEEP = colors.HexColor(S.DEEP)
C_CLAY = colors.HexColor(S.CLAY)
C_INK = colors.HexColor(S.INK)
C_MUTED = colors.HexColor(S.TEXT_MUTED)
C_HAIR = colors.HexColor(S.HAIRLINE)

MARGEN = 18 * mm


def _para_pdf(html: str) -> str:
    """Adapta el HTML ligero de narrativa.py al mini-markup de reportlab.

    reportlab acepta <b>/<i>/<font> pero no atributos de clase ni entidades
    arbitrarias, asi que los numeros resaltados pasan a <font color=arcilla>.
    """
    txt = re.sub(r'<b class="num">(.*?)</b>',
                 rf'<font color="{S.CLAY}"><b>\1</b></font>', html, flags=re.S)
    txt = txt.replace("&middot;", "&#183;").replace("&nbsp;", " ")
    # Las fuentes base de PDF (Helvetica/Times, WinAnsi) no traen estos glifos:
    # sin sustituirlos, reportlab cae a Symbol y el lector los pierde.
    for viejo, nuevo in [("→", "-&gt;"), ("×", "x"), ("ρ", "rho"), ("≥", "&gt;="),
                         ("≤", "&lt;="), ("≈", "~"), ("∿", "~"), ("⤓", "")]:
        txt = txt.replace(viejo, nuevo)
    return txt


def _estilos():
    base = getSampleStyleSheet()
    return {
        "portada_kicker": ParagraphStyle(
            "pk", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8.5,
            textColor=C_CLAY, spaceAfter=8, leading=11),
        "portada_titulo": ParagraphStyle(
            "pt", parent=base["Title"], fontName="Times-Bold", fontSize=26,
            textColor=C_DEEP, alignment=0, leading=30, spaceAfter=4),
        "portada_sub": ParagraphStyle(
            "ps", parent=base["Normal"], fontName="Helvetica", fontSize=10.5,
            textColor=C_MUTED, leading=15, spaceAfter=16),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Times-Bold", fontSize=16,
            textColor=C_DEEP, spaceBefore=4, spaceAfter=2, leading=19),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=8.5,
            textColor=C_CLAY, spaceBefore=10, spaceAfter=5, leading=11),
        "lead": ParagraphStyle(
            "lead", parent=base["Normal"], fontName="Times-Roman", fontSize=11,
            textColor=C_INK, leading=15.5, alignment=TA_JUSTIFY, spaceAfter=8),
        "bullet": ParagraphStyle(
            "bul", parent=base["Normal"], fontName="Helvetica", fontSize=9,
            textColor=C_INK, leading=13.5, alignment=TA_JUSTIFY,
            leftIndent=12, bulletIndent=2, spaceAfter=5,
            bulletFontName="Helvetica-Bold", bulletFontSize=8,
            bulletColor=C_CLAY),
        "nota": ParagraphStyle(
            "nota", parent=base["Normal"], fontName="Helvetica-Oblique", fontSize=8,
            textColor=C_MUTED, leading=11, spaceBefore=4),
        "celda": ParagraphStyle(
            "celda", parent=base["Normal"], fontName="Helvetica", fontSize=8,
            textColor=C_INK, leading=10),
    }


def _fondo(canvas, doc):
    """Lienzo crema + filete superior + pie con numero de pagina."""
    canvas.saveState()
    ancho, alto = A4
    canvas.setFillColor(C_CREAM)
    canvas.rect(0, 0, ancho, alto, stroke=0, fill=1)
    canvas.setFillColor(C_DEEP)
    canvas.rect(0, alto - 6 * mm, ancho, 6 * mm, stroke=0, fill=1)
    canvas.setFillColor(C_CLAY)
    canvas.rect(0, alto - 6 * mm, ancho * 0.28, 6 * mm, stroke=0, fill=1)

    canvas.setStrokeColor(C_HAIR)
    canvas.setLineWidth(0.6)
    canvas.line(MARGEN, 13 * mm, ancho - MARGEN, 13 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(C_MUTED)
    canvas.drawString(MARGEN, 9 * mm,
                      "Anatomia del riesgo de mercado  ·  Calma vs Crisis  ·  self-report")
    canvas.drawRightString(ancho - MARGEN, 9 * mm, f"Pagina {doc.page}")
    canvas.restoreState()


def _tabla(df, est, ancho_util):
    """DataFrame -> Table con la piel de la marca."""
    encabezado = [Paragraph(f"<b>{c}</b>", est["celda"]) for c in df.columns]
    cuerpo = [[Paragraph(str(v), est["celda"]) for v in fila]
              for fila in df.astype(str).values]
    t = Table([encabezado] + cuerpo, colWidths=[ancho_util / len(df.columns)] * len(df.columns),
              repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_DEEP),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_CREAM),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBF3EC")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, C_HAIR),
        ("BOX", (0, 0), (-1, -1), 0.6, C_HAIR),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _ficha_parametros(params, est, ancho_util):
    filas = [
        ("Rango de fechas", params["rango"]),
        ("Dias bursatiles en el rango", f"{params['n_dias']:,}"),
        ("Activos analizados", f"{params['n_activos']} — " + ", ".join(params["activos"])),
        ("Umbral de crisis", f"VIX > {params['umbral_vix']}"),
        ("Dias clasificados como crisis", f"{params['pct_crisis']:.1f}%"),
        ("Filtro de regimen", params["regimen_filtro"]),
        ("Activo en foco", params["foco"]),
    ]
    t = Table([[Paragraph(f"<b>{k}</b>", est["celda"]), Paragraph(v, est["celda"])]
               for k, v in filas],
              colWidths=[ancho_util * 0.34, ancho_util * 0.66], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EDF3F8")),
        ("BACKGROUND", (1, 0), (1, -1), colors.white),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, C_HAIR),
        ("BOX", (0, 0), (-1, -1), 0.6, C_HAIR),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def generar_pdf(params: dict, bloques: list, vista_actual: str = "") -> bytes:
    """Construye el PDF completo y lo devuelve como bytes listos para descargar.

    params  -- dict de narrativa.resumen_parametros()
    bloques -- lista de narrativa.Bloque, uno por pantalla (las seis)
    """
    est = _estilos()
    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGEN, rightMargin=MARGEN,
        topMargin=16 * mm, bottomMargin=18 * mm,
        title="Self-report — Anatomia del riesgo de mercado",
        author="Dashboard Calma vs Crisis",
    )
    ancho_util = A4[0] - 2 * MARGEN
    frame = Frame(doc.leftMargin, doc.bottomMargin, ancho_util,
                  A4[1] - doc.topMargin - doc.bottomMargin, id="cuerpo")
    doc.addPageTemplates([PageTemplate(id="std", frames=[frame], onPage=_fondo)])

    hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
    flow = []

    # --- Portada -------------------------------------------------------------
    flow += [
        Spacer(1, 10 * mm),
        Paragraph("SELF-REPORT GENERADO DESDE EL DASHBOARD", est["portada_kicker"]),
        Paragraph("Anatomia del riesgo de mercado", est["portada_titulo"]),
        Paragraph("Calma vs Crisis &mdash; que pasa con la diversificacion "
                  "cuando el mercado entra en panico", est["portada_sub"]),
        _ficha_parametros(params, est, ancho_util),
        Spacer(1, 6 * mm),
        Paragraph(
            "Este documento recoge las <b>seis pantallas</b> del tablero con los "
            "parametros de arriba, no solo la que estaba en pantalla al descargarlo"
            + (f" (era <b>{vista_actual}</b>)." if vista_actual else ".")
            + " Cada seccion trae la lectura guiada de ese grafico &mdash; las mismas "
              "frases que muestra la aplicacion, recalculadas para esta seleccion de "
              "activos &mdash; y la tabla de datos que la respalda.",
            est["lead"]),
        Paragraph(
            f"Generado el {hoy}. Fuente: Yahoo Finance (yfinance), datos 100% reales. "
            "El regimen se define con una regla objetiva sobre el VIX, no con una "
            "clasificacion institucional. Documento academico: no es asesoria de "
            "inversion.", est["nota"]),
        PageBreak(),
    ]

    # --- Resumen ejecutivo: el primer insight de cada pantalla ---------------
    flow.append(Paragraph("Resumen ejecutivo", est["h1"]))
    flow.append(Paragraph("UN HALLAZGO POR PANTALLA", est["h2"]))
    for b in bloques:
        if not b.insights:
            continue
        clave = b.insights[1] if len(b.insights) > 1 else b.insights[0]
        flow.append(Paragraph(f"<b>{b.titulo}.</b> {clave}", est["bullet"], bulletText="•"))
    flow.append(Spacer(1, 4 * mm))
    flow.append(Paragraph(
        "Las secciones siguientes desarrollan cada pantalla: como se lee el grafico, "
        "que dicen los numeros de esta seleccion concreta y la tabla de respaldo.",
        est["nota"]))
    flow.append(PageBreak())

    # --- Una seccion por pantalla -------------------------------------------
    for i, b in enumerate(bloques):
        bloque_flow = [
            Paragraph(f"{i + 1}. {b.titulo}", est["h1"]),
            Paragraph(b.eyebrow.upper(), est["h2"]),
            Paragraph(_para_pdf(b.lead), est["lead"]),
        ]
        flow += bloque_flow
        for p in b.puntos:
            flow.append(Paragraph(_para_pdf(p), est["bullet"], bulletText="•"))
        if b.tabla is not None and len(b.tabla):
            flow.append(Spacer(1, 4 * mm))
            flow.append(KeepTogether([
                Paragraph(b.tabla_titulo.upper() or "DATOS", est["h2"]),
                _tabla(b.tabla, est, ancho_util),
            ]))
        if i < len(bloques) - 1:
            flow.append(PageBreak())

    # --- Cierre metodologico -------------------------------------------------
    flow += [
        PageBreak(),
        Paragraph("Nota metodologica y limitaciones", est["h1"]),
        Paragraph("QUE HAY QUE SABER ANTES DE CITAR ESTAS CIFRAS", est["h2"]),
    ]
    for txt in [
        f"El regimen se define con una regla simple y reproducible: <b>VIX &gt; "
        f"{params['umbral_vix']} implica crisis</b>. Es un criterio del proyecto, no una "
        f"clasificacion oficial; cambiarlo en el sidebar recalcula todas las cifras de "
        f"este informe.",
        "Los precios son cierres ajustados por dividendos y splits. Yahoo Finance no es "
        "una fuente institucional y puede revisar su historico entre descargas, asi que "
        "las cifras pueden variar levemente entre dos generaciones de este PDF.",
        "BTC-USD cotiza 24/7 y se alinea al calendario bursatil; los activos con historia "
        "mas corta conservan su ventana real y los calculos son NaN-aware (sin recortar "
        "la muestra completa al activo mas joven).",
        "La correlacion se calcula sobre retornos logaritmicos diarios y exige un minimo "
        "de observaciones por regimen; cuando el recorte deja pocos dias de crisis, el "
        "propio informe lo advierte en la seccion correspondiente.",
        "Proyecto academico de visualizacion de datos. <b>No constituye asesoria de "
        "inversion.</b>",
    ]:
        flow.append(Paragraph(txt, est["bullet"], bulletText="•"))

    doc.build(flow)
    return buffer.getvalue()
