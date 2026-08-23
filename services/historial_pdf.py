"""
Genera el PDF del historial clínico completo de un paciente: datos generales
más todas las entradas (diagnóstico, tratamiento, notas) en orden cronológico.

A diferencia de la receta (un membrete de tamaño fijo), esto es contenido de
largo variable — puede haber una entrada o cincuenta — así que se arma con
Platypus (flowables) para que fluya solo a la siguiente página cuando haga falta.
"""

import io
import os
from datetime import date, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable,
                                 PageTemplate, Paragraph, Spacer, Table,
                                 TableStyle)

from services.auth import datos_clinica, logo_clinica
from services.constantes import TIPOS_MORDIDA, TIPOS_PACIENTE
from services.filtros import edad as _texto_edad
from services.filtros import fecha as _texto_fecha
from services.odontograma_pdf import dibujar_odontograma, leyenda_odontograma
from services.periodontograma_pdf import (dibujar_periodontograma,
                                          indices_periodontograma,
                                          leyenda_periodontograma)

AZUL = colors.HexColor("#162A5C")
VERDE = colors.HexColor("#2E8B6E")
ROJO = colors.HexColor("#D64545")
GRIS = colors.HexColor("#5C6D79")
GRIS_CLARO = colors.HexColor("#D8E2E7")

LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "img", "logo.jpg")


def _logo():
    """El logo de la clínica en sesión; si no subió ninguno, el del sistema."""
    datos = logo_clinica()
    if datos:
        return ImageReader(io.BytesIO(datos))
    if os.path.exists(LOGO_PATH):
        return ImageReader(LOGO_PATH)
    return None

ESTILOS = {
    "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=15,
                             textColor=AZUL, spaceAfter=2),
    "seccion": ParagraphStyle("seccion", fontName="Helvetica-Bold", fontSize=11,
                              textColor=AZUL, spaceBefore=14, spaceAfter=6),
    "etiqueta": ParagraphStyle("etiqueta", fontName="Helvetica-Bold", fontSize=8.5,
                               textColor=GRIS, leading=11),
    "valor": ParagraphStyle("valor", fontName="Helvetica", fontSize=9.5,
                            textColor=AZUL, leading=13),
    "cuerpo": ParagraphStyle("cuerpo", fontName="Helvetica", fontSize=9.5,
                             textColor=AZUL, leading=13.5),
    "cuerpo_gris": ParagraphStyle("cuerpo_gris", fontName="Helvetica", fontSize=9,
                                  textColor=GRIS, leading=12.5),
    "fecha_evento": ParagraphStyle("fecha_evento", fontName="Helvetica-Bold", fontSize=9.5,
                                   textColor=VERDE, leading=12),
}


def _fecha_iso_a_es(valor) -> str:
    if not valor:
        return "—"
    if isinstance(valor, (date, datetime)):
        return _texto_fecha(valor)
    return _texto_fecha(str(valor))


def _encabezado_pie(paciente):
    """Devuelve la función on_page que dibuja membrete + pie en cada página."""
    def dibujar(c, doc):
        ancho, alto = A4
        margen = doc.leftMargin

        c.saveState()
        logo = _logo()
        if logo:
            lado = 34
            c.drawImage(logo, margen, alto - margen - lado + 6,
                        width=lado, height=lado, preserveAspectRatio=True, mask="auto")
            tx = margen + lado + 10
        else:
            tx = margen

        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(AZUL)
        c.drawString(tx, alto - margen - 8, datos_clinica()["nombre"])
        c.setFont("Helvetica", 8)
        c.setFillColor(GRIS)
        c.drawString(tx, alto - margen - 20, "Historial clínico odontológico")

        c.setFont("Helvetica", 8)
        c.setFillColor(GRIS)
        # Aquí sí hay ancho de A4, así que los números caben en una sola línea.
        clinica = datos_clinica()
        c.drawRightString(ancho - margen, alto - margen - 8,
                          "  ·  ".join(clinica["telefonos"]))
        c.drawRightString(ancho - margen, alto - margen - 20, clinica["direccion"])

        c.setStrokeColor(GRIS_CLARO)
        c.setLineWidth(1)
        c.line(margen, alto - margen - 32, ancho - margen, alto - margen - 32)

        # Pie de página
        c.setFont("Helvetica", 7.5)
        c.setFillColor(GRIS)
        generado = datetime.now().strftime("%d/%m/%Y %H:%M")
        c.drawString(margen, margen - 18, f"Generado el {generado}  ·  Paciente: {paciente.get('nombre', '')}")
        c.drawRightString(ancho - margen, margen - 18, f"Página {c.getPageNumber()}")
        c.restoreState()
    return dibujar


def _fila_dato(etiqueta, valor):
    return [Paragraph(etiqueta, ESTILOS["etiqueta"]), Paragraph(valor or "—", ESTILOS["valor"])]


def generar_historial_pdf(paciente: dict, entradas: list,
                          odontograma: dict | None = None,
                          odontograma_caras: dict | None = None,
                          periodontograma: dict | None = None) -> bytes:
    """
    paciente: fila de "pacientes".
    entradas: filas de "historial" (con o sin historial_imagenes embebidas),
              ya ordenadas como se quieran mostrar (normalmente más reciente primero).
    odontograma / odontograma_caras: mismo formato que se le pasa al JS de la
              ficha web ({"11": {"estado":..., "perno":...}}, {"11": {"oclusal":...}}).
    periodontograma: la fila más reciente de "periodontogramas", o None si el
              paciente no tiene ninguno (entonces la sección no se imprime).
    Devuelve los bytes del PDF.
    """
    buffer = io.BytesIO()
    margen = 20 * mm

    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=margen, rightMargin=margen, topMargin=margen + 26, bottomMargin=margen,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    plantilla = PageTemplate(id="con_membrete", frames=[frame], onPage=_encabezado_pie(paciente))
    doc.addPageTemplates([plantilla])

    story = []
    story.append(Paragraph("Historia clínica", ESTILOS["titulo"]))
    story.append(Paragraph(paciente.get("nombre") or "", ParagraphStyle(
        "nombre_paciente", fontName="Helvetica-Bold", fontSize=18, textColor=AZUL, spaceAfter=10)))

    # ---- Odontograma actual (arriba de todo) ---------------------------------
    story.append(Paragraph("Odontograma", ESTILOS["seccion"]))
    dibujo = dibujar_odontograma(
        odontograma or {}, odontograma_caras or {},
        paciente.get("tipo_paciente") or "adulto",
    )
    # Se escala al ancho útil de la página. OJO: Drawing.scale() solo
    # transforma el contenido — hay que agrandar width/height a mano o
    # Platypus sigue reservando (y recortando a) el tamaño original.
    escala = min(1.6, doc.width / dibujo.width)
    dibujo.scale(escala, escala)
    dibujo.width *= escala
    dibujo.height *= escala
    dibujo.hAlign = "CENTER"
    story.append(dibujo)
    story.append(Spacer(1, 4))

    filas_leyenda = [leyenda_odontograma()[i:i + 4] for i in range(0, len(leyenda_odontograma()), 4)]
    for fila in filas_leyenda:
        celdas = []
        for color_hex, etiqueta in fila:
            muestra = Table([[""]], colWidths=[7], rowHeights=[7])
            muestra.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(color_hex)),
                ("BOX", (0, 0), (-1, -1), 0.4, GRIS_CLARO),
            ]))
            celdas.append(muestra)
            celdas.append(Paragraph(etiqueta, ESTILOS["cuerpo_gris"]))
        fila_tabla = Table([celdas], colWidths=None)
        fila_tabla.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(fila_tabla)
    story.append(Spacer(1, 14))

    # ---- Periodontograma (solo si el paciente tiene uno) ---------------------
    # Va inmediatamente después del odontograma porque son las dos cartas que
    # se leen juntas: una dice qué pieza tratar, la otra en qué estado está el
    # soporte que la sostiene.
    if periodontograma:
        story.append(Paragraph("Periodontograma", ESTILOS["seccion"]))
        story.append(Paragraph(
            f"Registrado el {_texto_fecha(periodontograma.get('fecha'))}",
            ESTILOS["cuerpo_gris"]))
        story.append(Spacer(1, 4))

        carta = dibujar_periodontograma(
            periodontograma.get("datos") or {},
            paciente.get("tipo_paciente") or "adulto",
        )
        # Mismo cuidado que con el odontograma: scale() no toca width/height y
        # Platypus seguiría reservando el tamaño original.
        escala_p = min(1.6, doc.width / carta.width)
        carta.scale(escala_p, escala_p)
        carta.width *= escala_p
        carta.height *= escala_p
        carta.hAlign = "CENTER"
        story.append(carta)
        story.append(Spacer(1, 4))

        celdas_leyenda = []
        for color_hex, etiqueta in leyenda_periodontograma():
            muestra = Table([[""]], colWidths=[7], rowHeights=[7])
            muestra.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(color_hex)),
                ("BOX", (0, 0), (-1, -1), 0.4, GRIS_CLARO),
            ]))
            celdas_leyenda.append(muestra)
            celdas_leyenda.append(Paragraph(etiqueta, ESTILOS["cuerpo_gris"]))
        tabla_leyenda = Table([celdas_leyenda])
        tabla_leyenda.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tabla_leyenda)
        story.append(Spacer(1, 6))

        indices = indices_periodontograma(periodontograma)
        tabla_indices = Table(
            [[Paragraph(e, ESTILOS["etiqueta"]) for e, _ in indices],
             [Paragraph(v, ESTILOS["valor"]) for _, v in indices]],
            colWidths=[doc.width / len(indices)] * len(indices),
        )
        tabla_indices.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEABOVE", (0, 0), (-1, 0), 0.5, GRIS_CLARO),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, GRIS_CLARO),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tabla_indices)
        story.append(Spacer(1, 14))

    # ---- Datos generales -----------------------------------------------------
    edad_txt = _texto_edad(paciente.get("fecha_nac"))
    tipo_txt = TIPOS_PACIENTE.get(paciente.get("tipo_paciente") or "adulto", "Adulto")
    tabla_datos = Table([
        _fila_dato("DOCUMENTO", paciente.get("documento")),
        _fila_dato("FECHA DE NACIMIENTO / EDAD",
                   f"{_fecha_iso_a_es(paciente.get('fecha_nac'))} · {edad_txt}" if paciente.get("fecha_nac") else "—"),
        _fila_dato("TELÉFONO", paciente.get("telefono")),
        _fila_dato("EMAIL", paciente.get("email")),
        _fila_dato("DIRECCIÓN", paciente.get("direccion")),
        _fila_dato("TIPO DE PACIENTE", tipo_txt),
        _fila_dato("TIPO DE MORDIDA", TIPOS_MORDIDA.get(paciente.get("mordida"), "Sin evaluar")),
    ], colWidths=[46 * mm, doc.width - 46 * mm])
    tabla_datos.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, GRIS_CLARO),
    ]))
    story.append(tabla_datos)
    story.append(Spacer(1, 10))

    # ---- Alergias: banner verde o rojo, igual que en la ficha web -----------
    alergias = paciente.get("alergias")
    color_banner = ROJO if alergias else VERDE
    fondo_banner = colors.HexColor("#FBEAEA") if alergias else colors.HexColor("#E6F4EF")
    texto_banner = f"Alergias: {alergias}" if alergias else "Alergias: Sin alergias"
    tabla_alergia = Table([[Paragraph(texto_banner, ParagraphStyle(
        "alergia", fontName="Helvetica-Bold", fontSize=9.5, textColor=color_banner))]],
        colWidths=[doc.width])
    tabla_alergia.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fondo_banner),
        ("BOX", (0, 0), (-1, -1), 0.6, color_banner),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(tabla_alergia)

    # ---- Historial clínico: una entrada por evento --------------------------
    story.append(Paragraph(f"Historial clínico · {len(entradas)} entrada(s)", ESTILOS["seccion"]))

    if not entradas:
        story.append(Paragraph("Sin entradas registradas.", ESTILOS["cuerpo_gris"]))
    else:
        for i, e in enumerate(entradas):
            story.append(Paragraph(_fecha_iso_a_es(e.get("fecha")), ESTILOS["fecha_evento"]))
            if e.get("diagnostico"):
                story.append(Paragraph(f"<b>Diagnóstico:</b> {e['diagnostico']}", ESTILOS["cuerpo"]))
            if e.get("tratamiento"):
                story.append(Paragraph(f"<b>Tratamiento:</b> {e['tratamiento']}", ESTILOS["cuerpo"]))
            if e.get("notas"):
                story.append(Paragraph(e["notas"], ESTILOS["cuerpo_gris"]))
            imagenes = e.get("historial_imagenes") or []
            if imagenes:
                story.append(Paragraph(
                    f"{len(imagenes)} imagen(es) adjunta(s) — disponibles en el sistema.",
                    ESTILOS["cuerpo_gris"]))
            if i < len(entradas) - 1:
                story.append(Spacer(1, 4))
                story.append(HRFlowable(width="100%", thickness=0.4, color=GRIS_CLARO,
                                        spaceBefore=2, spaceAfter=10))

    doc.build(story)
    return buffer.getvalue()
