"""
Genera el PDF de una receta médica con el membrete de la clínica.

Se arma con reportlab directamente sobre un canvas (no con Platypus) porque
el diseño es un membrete fijo, no un documento fluido: es más simple ubicar
cada bloque a mano que armar flowables para una sola página.

Los adornos (ondas, destellos, marca de agua) son un acercamiento vectorial
a la plantilla de diseño de la clínica, no una réplica exacta pixel a pixel.
"""

import io
import math
import os
from datetime import date, datetime

from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from services.constantes import CLINICA
from services.filtros import edad as _texto_edad

AZUL = (0x16 / 255, 0x2A / 255, 0x5C / 255)      # navy de la marca
AZUL_OSCURO = (0x0E / 255, 0x1B / 255, 0x3D / 255)
VERDE = (0x4C / 255, 0xAE / 255, 0x92 / 255)     # teal/verde de la marca
VERDE_OSCURO = (0x2E / 255, 0x8B / 255, 0x6E / 255)
GRIS_TEXTO = (0x5C / 255, 0x6D / 255, 0x79 / 255)
BLANCO = (1, 1, 1)

CARPETA_IMG = os.path.join(os.path.dirname(__file__), "..", "static", "img")
LOGO_PATH = os.path.join(CARPETA_IMG, "logo.jpg")

_FUENTE_SCRIPT = "Helvetica-Oblique"   # se reemplaza si se logra registrar la cursiva
for _nombre_win in ("BRUSHSCI.TTF", "brushsci.ttf"):
    _ruta = os.path.join("C:\\Windows\\Fonts", _nombre_win)
    if os.path.exists(_ruta):
        try:
            pdfmetrics.registerFont(TTFont("BrushScript", _ruta))
            _FUENTE_SCRIPT = "BrushScript"
        except Exception:
            pass
        break

_marca_agua_cache: bytes | None = None


def _marca_agua_logo() -> "ImageReader | None":
    """
    Versión desvanecida del logo para usar como marca de agua dentro de la
    caja "Rp.", igual que en la plantilla de referencia. Se calcula una sola
    vez por proceso (no en cada receta) y se cachea en memoria.
    """
    global _marca_agua_cache
    if _marca_agua_cache is not None:
        return ImageReader(io.BytesIO(_marca_agua_cache))
    if not os.path.exists(LOGO_PATH):
        return None

    logo = Image.open(LOGO_PATH).convert("RGB")
    salida = Image.new("RGBA", logo.size, (0, 0, 0, 0))
    origen = logo.load()
    destino = salida.load()
    for y in range(logo.height):
        for x in range(logo.width):
            r, g, b = origen[x, y]
            oscuridad = 255 - min(r, g, b)     # 0 en el blanco de fondo, alto donde hay tinta
            alpha = min(255, int(oscuridad * 0.16))
            destino[x, y] = (0x9F, 0xB3, 0xC9, alpha)

    buffer = io.BytesIO()
    salida.save(buffer, format="PNG")
    _marca_agua_cache = buffer.getvalue()
    return ImageReader(io.BytesIO(_marca_agua_cache))


def _fecha_es(valor) -> str:
    """dd/mm/aaaa, sin depender de la configuración regional del sistema.
    Supabase devuelve la fecha como texto ISO ('2026-08-20'), no como date."""
    if not valor:
        return "__ / __ / ____"
    if isinstance(valor, (date, datetime)):
        dt = valor
    else:
        dt = date.fromisoformat(str(valor)[:10])
    return dt.strftime("%d / %m / %Y")


# -----------------------------------------------------------------------
# Adornos vectoriales: ondas de esquina, destellos, íconos
# -----------------------------------------------------------------------
def _onda_esquina(c, ancho, alto):
    """Cintas curvas superpuestas en la esquina superior izquierda."""
    c.saveState()
    p = c.beginPath()
    p.moveTo(0, alto)
    p.curveTo(0, alto - 90, 60, alto - 70, 110, alto - 130)
    p.curveTo(160, alto - 190, 90, alto - 230, 0, alto - 210)
    p.close()
    c.setFillColorRGB(*VERDE)
    c.setFillAlpha(0.35)
    c.drawPath(p, fill=1, stroke=0)

    p2 = c.beginPath()
    p2.moveTo(0, alto)
    p2.curveTo(40, alto - 40, 40, alto - 110, 0, alto - 150)
    p2.close()
    c.setFillColorRGB(*AZUL)
    c.setFillAlpha(0.22)
    c.drawPath(p2, fill=1, stroke=0)
    c.restoreState()


def _onda_pie(c, ancho):
    """Franja curva oscura en el pie de la página, como cierre de la plantilla.
    Se mantiene baja (máx. ~34pt) para no pisar el texto del pie."""
    c.saveState()
    p = c.beginPath()
    p.moveTo(0, 0)
    p.lineTo(0, 30)
    p.curveTo(ancho * 0.35, 46, ancho * 0.4, 6, ancho * 0.68, 18)
    p.curveTo(ancho * 0.85, 26, ancho * 0.93, 4, ancho, 12)
    p.lineTo(ancho, 0)
    p.close()
    c.setFillColorRGB(*AZUL_OSCURO)
    c.setFillAlpha(1)
    c.drawPath(p, fill=1, stroke=0)

    p2 = c.beginPath()
    p2.moveTo(0, 0)
    p2.lineTo(0, 16)
    p2.curveTo(ancho * 0.3, 24, ancho * 0.5, 2, ancho * 0.75, 9)
    p2.curveTo(ancho * 0.9, 14, ancho * 0.95, 1, ancho, 6)
    p2.lineTo(ancho, 0)
    p2.close()
    c.setFillColorRGB(*VERDE)
    c.setFillAlpha(0.55)
    c.drawPath(p2, fill=1, stroke=0)
    c.restoreState()


def _destello(c, cx, cy, r, color=AZUL):
    """Un pequeño destello de 4 puntas, como los de la plantilla original."""
    c.saveState()
    c.setFillColorRGB(*color)
    p = c.beginPath()
    puntos = [(0, r), (r * 0.22, r * 0.22), (r, 0),
              (r * 0.22, -r * 0.22), (0, -r), (-r * 0.22, -r * 0.22),
              (-r, 0), (-r * 0.22, r * 0.22)]
    p.moveTo(cx + puntos[0][0], cy + puntos[0][1])
    for dx, dy in puntos[1:]:
        p.lineTo(cx + dx, cy + dy)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()


def _icono_whatsapp(c, cx, cy, r):
    """Círculo verde con un globo de chat simple (bastan para leerse como 'WhatsApp')."""
    c.saveState()
    c.setFillColorRGB(*VERDE_OSCURO)
    c.circle(cx, cy, r, fill=1, stroke=0)

    bw, bh = r * 1.05, r * 0.78
    bx, by = cx - bw / 2, cy - bh / 2 + r * 0.12
    c.setFillColorRGB(*BLANCO)
    c.roundRect(bx, by, bw, bh, bh * 0.4, fill=1, stroke=0)
    cola = c.beginPath()
    cola.moveTo(bx + bw * 0.28, by)
    cola.lineTo(bx + bw * 0.16, by - r * 0.32)
    cola.lineTo(bx + bw * 0.5, by)
    cola.close()
    c.drawPath(cola, fill=1, stroke=0)

    c.setFillColorRGB(*VERDE_OSCURO)
    for i in (-1, 0, 1):
        c.circle(cx + i * bw * 0.2, by + bh * 0.5, r * 0.09, fill=1, stroke=0)
    c.restoreState()


def _icono_ubicacion(c, cx, cy_top, r):
    """Pin de ubicación clásico: bulto redondeado arriba, punta hacia abajo.
    cy_top = altura del centro del bulto redondeado (la punta cuelga debajo)."""
    c.saveState()
    c.setFillColorRGB(*AZUL)
    punta_y = cy_top - r * 2.2
    p = c.beginPath()
    p.moveTo(cx - r, cy_top)
    p.curveTo(cx - r, cy_top + r * 0.9, cx + r, cy_top + r * 0.9, cx + r, cy_top)
    p.curveTo(cx + r, cy_top - r * 0.9, cx + r * 0.3, cy_top - r * 1.6, cx, punta_y)
    p.curveTo(cx - r * 0.3, cy_top - r * 1.6, cx - r, cy_top - r * 0.9, cx - r, cy_top)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.setFillColorRGB(*BLANCO)
    c.circle(cx, cy_top, r * 0.4, fill=1, stroke=0)
    c.restoreState()


def _icono_diente_simple(c, cx, cy, r, color):
    """Silueta redondeada de diente, para el sello circular del pie."""
    c.saveState()
    c.setFillColorRGB(*color)
    p = c.beginPath()
    p.moveTo(cx - r, cy + r * 0.5)
    p.curveTo(cx - r, cy + r * 1.1, cx - r * 0.3, cy + r, cx, cy + r * 0.55)
    p.curveTo(cx + r * 0.3, cy + r, cx + r, cy + r * 1.1, cx + r, cy + r * 0.5)
    p.curveTo(cx + r, cy - r * 0.3, cx + r * 0.35, cy - r * 1.2, cx, cy - r * 1.2)
    p.curveTo(cx - r * 0.35, cy - r * 1.2, cx - r, cy - r * 0.3, cx - r, cy + r * 0.5)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()


def _dibujar_bloque(c, x0, y0, w, h, receta, paciente, etiqueta_copia):
    """
    Dibuja una receta completa dentro de la caja (x0, y0, w, h) — (x0, y0) es
    la esquina inferior izquierda. Se usa dos veces por página (paciente y
    odontólogo) en el formato de media hoja apaisada.
    """
    x1 = x0 + w
    y1 = y0 + h
    y = y1

    # ---- Encabezado: logo a la izquierda, contacto a la derecha -----------
    logo_lado = 46
    if os.path.exists(LOGO_PATH):
        c.drawImage(ImageReader(LOGO_PATH), x0, y - logo_lado,
                    width=logo_lado, height=logo_lado,
                    preserveAspectRatio=True, mask="auto")

    tx = x0 + logo_lado + 8
    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(*AZUL)
    c.drawString(tx, y - 15, CLINICA["nombre"])
    c.setFont("Helvetica", 6)
    c.setFillColorRGB(*VERDE_OSCURO)
    c.drawString(tx, y - 24, "C O N S U L T O R I O   O D O N T O L Ó G I C O")
    c.setFont(_FUENTE_SCRIPT, 10)
    c.setFillColorRGB(*AZUL)
    c.drawString(tx, y - 38, "Sonrisas sanas y brillantes")

    # -- Contacto (derecha) --
    icono_r = 7
    icono_cx = x1 - 90
    _icono_whatsapp(c, icono_cx, y - 8, icono_r)
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColorRGB(*AZUL)
    c.drawString(icono_cx + 12, y - 10, CLINICA["celular"])

    _icono_ubicacion(c, icono_cx + 3, y - 26, 4)
    c.setFont("Helvetica", 6.3)
    c.setFillColorRGB(*AZUL)
    c.drawString(icono_cx + 12, y - 25, CLINICA["direccion"].split(",")[0])
    resto_direccion = ",".join(CLINICA["direccion"].split(",")[1:]).strip()
    if resto_direccion:
        c.drawString(icono_cx + 12, y - 33, resto_direccion)

    y -= logo_lado + 12

    # ---- Banner "RECETA MÉDICA" + etiqueta de copia ------------------------
    banner_alto = 20
    c.setFillColorRGB(*AZUL)
    c.roundRect(x0, y - banner_alto, w, banner_alto, 10, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(*BLANCO)
    c.drawCentredString((x0 + x1) / 2, y - banner_alto + 6.5, "RECETA MÉDICA")
    _destello(c, x0 - 4, y - banner_alto / 2, 5, AZUL)
    _destello(c, x1 + 4, y - banner_alto / 2, 5, AZUL)
    y -= banner_alto + 8

    c.setFont("Helvetica-Oblique", 7)
    c.setFillColorRGB(*GRIS_TEXTO)
    c.drawCentredString((x0 + x1) / 2, y, f"— Copia: {etiqueta_copia} —")
    y -= 16

    # ---- Datos del paciente -------------------------------------------------
    def campo(x, label, valor, ancho_linea, tam=8):
        c.setFont("Helvetica-Bold", tam)
        c.setFillColorRGB(*AZUL)
        c.drawString(x, y, label)
        lx = x + c.stringWidth(label, "Helvetica-Bold", tam) + 3
        c.setStrokeColorRGB(*AZUL)
        c.setLineWidth(0.6)
        c.line(lx, y - 1.5, lx + ancho_linea, y - 1.5)
        c.setFont("Helvetica", tam)
        c.setFillColorRGB(*AZUL)
        c.drawString(lx + 2, y, valor)

    mitad = w * 0.6
    campo(x0, "Paciente:", paciente.get("nombre") or "", mitad)
    campo(x0 + mitad + 14, "Fecha:", _fecha_es(receta.get("fecha")), w - mitad - 14 - 34)
    y -= 15

    edad_txt = _texto_edad(paciente.get("fecha_nac"))
    tercio = w / 3
    campo(x0, "Edad:", edad_txt if edad_txt != "—" else "", tercio - 30)
    campo(x0 + tercio, "DNI:", paciente.get("documento") or "", tercio - 30)
    campo(x0 + tercio * 2, "Tel:", paciente.get("telefono") or "", tercio - 26)
    y -= 12

    # ---- Caja "Rp." con la prescripción --------------------------------------
    pie_caja = 62        # deja espacio para firma (3 líneas) + footer
    caja_top = y
    caja_bottom = y0 + pie_caja
    c.setStrokeColorRGB(*VERDE_OSCURO)
    c.setLineWidth(1.1)
    c.roundRect(x0, caja_bottom, w, caja_top - caja_bottom, 10, fill=0, stroke=1)

    marca_agua = _marca_agua_logo()
    if marca_agua:
        lado_marca = min(w, caja_top - caja_bottom) * 0.55
        c.drawImage(marca_agua,
                    (x0 + x1) / 2 - lado_marca / 2,
                    (caja_top + caja_bottom) / 2 - lado_marca / 2,
                    width=lado_marca, height=lado_marca,
                    preserveAspectRatio=True, mask="auto")

    c.setFont(_FUENTE_SCRIPT, 16)
    c.setFillColorRGB(*AZUL)
    c.drawString(x0 + 12, caja_top - 20, "Rp.")

    texto = c.beginText(x0 + 14, caja_top - 38)
    texto.setFont("Helvetica", 8.3)
    texto.setFillColorRGB(*AZUL)
    texto.setLeading(11.5)
    ancho_texto = w - 26
    for parrafo in (receta.get("contenido") or "").split("\n"):
        for linea in _envolver_texto(c, parrafo, "Helvetica", 8.3, ancho_texto):
            texto.textLine(linea)
        texto.textLine("")
    c.drawText(texto)

    # Firma dentro de la caja, pegada a la base.
    # Estructura oficial del sello (CCDP): nombre completo / profesión / Reg. CCDP N.°
    firma_y = caja_bottom + 28
    c.setStrokeColorRGB(*AZUL)
    c.line(x1 - 150, firma_y, x1 - 12, firma_y)
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColorRGB(*AZUL)
    c.drawCentredString(x1 - 81, firma_y - 9,
                        receta.get("odontologo_nombre") or "Odontólogo(a)")
    c.setFont("Helvetica", 6.3)
    c.setFillColorRGB(*AZUL)
    c.drawCentredString(x1 - 81, firma_y - 17, "Cirujano Dentista")
    c.setFont("Helvetica", 6)
    c.setFillColorRGB(*GRIS_TEXTO)
    c.drawCentredString(x1 - 81, firma_y - 25,
                        f"Reg. CCDP N.° {receta.get('odontologo_cop') or '_______'}")

    # ---- Pie de la ficha ----------------------------------------------------
    _icono_diente_simple(c, x0 + 9, y0 + 10, 6, VERDE_OSCURO)
    c.setFont("Helvetica", 5.6)
    c.setFillColorRGB(*GRIS_TEXTO)
    c.drawCentredString((x0 + x1) / 2 + 6, y0 + 8,
                        "Atención personalizada  ·  Tratamientos de calidad  ·  Cuidado para toda la familia")


def _linea_de_corte(c, x, y0, y1):
    """Línea punteada vertical en el centro de la hoja, para cortar en dos."""
    c.saveState()
    c.setStrokeColorRGB(*GRIS_TEXTO)
    c.setLineWidth(0.7)
    c.setDash(3, 4)
    c.line(x, y0, x, y1)
    c.restoreState()

    c.saveState()
    c.translate(x, (y0 + y1) / 2)
    c.rotate(90)
    c.setFont("Helvetica", 6.5)
    c.setFillColorRGB(*GRIS_TEXTO)
    c.drawCentredString(0, 4, "· · ·  cortar aquí  · · ·")
    c.restoreState()


def generar_receta_pdf(receta: dict, paciente: dict) -> bytes:
    """
    Genera una hoja A4 apaisada con DOS copias idénticas de la receta, una
    junto a la otra, separadas por una línea de corte — una para el
    paciente y otra para que el odontólogo se quede con copia física.

    receta:   fila de la tabla "recetas" (contenido, fecha, odontologo_*).
    paciente: fila de la tabla "pacientes" (nombre, documento, telefono, fecha_nac).
    Devuelve los bytes del PDF, listos para servir o guardar.
    """
    buffer = io.BytesIO()
    ancho, alto = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=(ancho, alto))

    margen = 24
    gap = 22
    col_w = (ancho - 2 * margen - gap) / 2
    col_h = alto - 2 * margen
    y0 = margen

    x_izq = margen
    x_der = margen + col_w + gap

    _onda_esquina(c, ancho, alto)

    _dibujar_bloque(c, x_izq, y0, col_w, col_h, receta, paciente, "Paciente")
    _dibujar_bloque(c, x_der, y0, col_w, col_h, receta, paciente, "Odontólogo(a)")
    _linea_de_corte(c, ancho / 2, margen * 0.4, alto - margen * 0.4)

    c.showPage()
    c.save()
    return buffer.getvalue()


def _envolver_texto(c, texto, fuente, tamano, ancho_max):
    """Corta un párrafo en líneas que quepan en ancho_max puntos."""
    palabras = texto.split(" ")
    lineas, actual = [], ""
    for palabra in palabras:
        candidata = f"{actual} {palabra}".strip()
        if c.stringWidth(candidata, fuente, tamano) <= ancho_max:
            actual = candidata
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas or [""]
