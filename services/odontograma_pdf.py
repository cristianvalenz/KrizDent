"""
Dibuja el odontograma como una imagen vectorial (reportlab.graphics) para
incrustarla en el PDF del historial clínico. Es una versión simplificada del
diagrama interactivo de static/js/odontograma.js: mismas 5 caras por pieza y
los mismos colores, sin la silueta anatómica decorativa (no aporta en papel).
"""

from reportlab.graphics.shapes import Drawing, Group, Line, Polygon, Rect, String
from reportlab.lib import colors

from services.constantes import CARAS_PIEZA, ESTADOS_CARA, ESTADOS_PIEZA

FILA_SUPERIOR_ADULTO = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
FILA_INFERIOR_ADULTO = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
FILA_SUPERIOR_NINO = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65]
FILA_INFERIOR_NINO = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75]

RADIO = 8            # mitad del lado del cuadro de cada pieza
SEPARACION = 3
MARGEN_IZQ = 6
SEPARACION_ARCADAS = 7
Y_SUPERIOR = 40
Y_INFERIOR = 14
NUM_OFFSET = 11       # distancia del número al cuadro, hacia la línea media


def _color(hexadecimal: str) -> colors.Color:
    return colors.HexColor(hexadecimal)


def _centro_x(i: int, por_hemiarco: int) -> float:
    paso = 2 * RADIO + SEPARACION
    return MARGEN_IZQ + RADIO + i * paso + (SEPARACION_ARCADAS if i >= por_hemiarco else 0)


def _poligonos_caras(cx, cy, lado):
    mitad = lado / 2
    li = lado * 0.21
    TL, TR = (cx - mitad, cy + mitad), (cx + mitad, cy + mitad)
    BL, BR = (cx - mitad, cy - mitad), (cx + mitad, cy - mitad)
    iTL, iTR = (cx - li, cy + li), (cx + li, cy + li)
    iBL, iBR = (cx - li, cy - li), (cx + li, cy - li)
    return {
        "vestibular": [TL, TR, iTR, iTL],
        "lingual": [BL, BR, iBR, iBL],
        "mesial": [TL, BL, iBL, iTL],
        "distal": [TR, BR, iBR, iTR],
        "oclusal": [iTL, iTR, iBR, iBL],
    }


def _agregar_pieza(grupo, fdi, cx, cy, es_superior, estado_pieza, caras_pieza, con_perno):
    lado = 2 * RADIO

    info_pieza = ESTADOS_PIEZA.get(estado_pieza, ESTADOS_PIEZA["sano"])
    es_estado_pieza_completo = estado_pieza != "sano"

    for nombre, puntos in _poligonos_caras(cx, cy, lado).items():
        if es_estado_pieza_completo:
            color = _color(info_pieza["color"])
        else:
            estado_cara = caras_pieza.get(nombre, "sano")
            color = _color(ESTADOS_CARA.get(estado_cara, ESTADOS_CARA["sano"])["color"])
        poligono = Polygon(
            points=[coord for punto in puntos for coord in punto],
            fillColor=color, strokeColor=_color("#C6D0D6"), strokeWidth=0.4,
        )
        grupo.add(poligono)

    grupo.add(Rect(cx - RADIO, cy - RADIO, lado, lado,
                   fillColor=None, strokeColor=_color("#A9BAC4"), strokeWidth=0.7))

    if estado_pieza == "ausente":
        d = RADIO * 0.75
        grupo.add(Line(cx - d, cy - d, cx + d, cy + d, strokeColor=_color("#5A6B76"), strokeWidth=1))
        grupo.add(Line(cx - d, cy + d, cx + d, cy - d, strokeColor=_color("#5A6B76"), strokeWidth=1))

    if con_perno:
        signo = -1 if es_superior else 1
        grupo.add(Line(cx, cy + signo * RADIO, cx, cy + signo * (RADIO + 4),
                       strokeColor=_color("#16232E"), strokeWidth=1.4))

    y_numero = cy + (NUM_OFFSET if es_superior else -NUM_OFFSET)
    grupo.add(String(cx, y_numero - 2.2, str(fdi), fontName="Helvetica", fontSize=5.4,
                     fillColor=_color("#5C6D79"), textAnchor="middle"))


def dibujar_odontograma(estados: dict, caras: dict, tipo_paciente: str) -> Drawing:
    """
    estados: {"11": {"estado": "caries", "perno": False}, ...} — igual formato
             que se le pasa al JS en la ficha del paciente.
    caras:   {"11": {"oclusal": "caries", ...}, ...}
    """
    es_nino = tipo_paciente == "nino"
    fila_sup = FILA_SUPERIOR_NINO if es_nino else FILA_SUPERIOR_ADULTO
    fila_inf = FILA_INFERIOR_NINO if es_nino else FILA_INFERIOR_ADULTO
    por_hemiarco = 5 if es_nino else 8

    ancho = _centro_x(len(fila_sup) - 1, por_hemiarco) + MARGEN_IZQ + RADIO
    alto = Y_SUPERIOR + RADIO + NUM_OFFSET + 6

    drawing = Drawing(ancho, alto)
    grupo = Group()

    x_medio = (_centro_x(por_hemiarco - 1, por_hemiarco) + _centro_x(por_hemiarco, por_hemiarco)) / 2
    grupo.add(Line(x_medio, 2, x_medio, alto - 2, strokeColor=_color("#D8E2E7"), strokeWidth=0.6))
    grupo.add(Line(MARGEN_IZQ - 6, (Y_SUPERIOR + Y_INFERIOR) / 2, ancho - MARGEN_IZQ + 6,
                   (Y_SUPERIOR + Y_INFERIOR) / 2, strokeColor=_color("#D8E2E7"), strokeWidth=0.6))

    for i, fdi in enumerate(fila_sup):
        cx = _centro_x(i, por_hemiarco)
        info = estados.get(str(fdi), {})
        _agregar_pieza(grupo, fdi, cx, Y_SUPERIOR, True,
                       info.get("estado", "sano"), caras.get(str(fdi), {}), info.get("perno", False))

    for i, fdi in enumerate(fila_inf):
        cx = _centro_x(i, por_hemiarco)
        info = estados.get(str(fdi), {})
        _agregar_pieza(grupo, fdi, cx, Y_INFERIOR, False,
                       info.get("estado", "sano"), caras.get(str(fdi), {}), info.get("perno", False))

    drawing.add(grupo)
    return drawing


def leyenda_odontograma():
    """Lista [(color, etiqueta), ...] para pintar debajo del diagrama."""
    orden = ["sano", "caries", "obturado", "obturado_mal", "ausente",
             "corona_buena", "corona_mala", "remanente_radicular"]
    fuente = {**ESTADOS_PIEZA, **ESTADOS_CARA}
    return [(fuente[c]["color"], fuente[c]["etiqueta"]) for c in orden if c in fuente]
