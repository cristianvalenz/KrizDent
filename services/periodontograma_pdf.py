"""
Dibuja la carta periodontal para incrustarla en el PDF de la historia clínica.

Sigue el mismo criterio que services/odontograma_pdf.py: en papel se dibujan
los DATOS, no la anatomía. Los dientes de la versión web ayudan a ubicarse en
pantalla mientras se registra; impresos solo gastarían tinta y comprimirían la
única información que importa aquí — a qué profundidad está el fondo de bolsa
en cada sitio.

Se grafican los 3 sitios por cara (6 por pieza), que es lo que distingue a un
periodontograma: promediarlos escondería justo la bolsa profunda aislada que
uno necesita ver.
"""

from reportlab.graphics.shapes import Circle, Drawing, Group, Line, PolyLine, String
from reportlab.lib import colors

FILA_SUPERIOR_ADULTO = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
FILA_INFERIOR_ADULTO = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
FILA_SUPERIOR_NINO = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65]
FILA_INFERIOR_NINO = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75]

CARAS = ("vestibular", "palatina")
SITIOS = (0, 1, 2)

ROJO = colors.HexColor("#D64545")     # sangrado
AZUL = colors.HexColor("#1B6E8C")     # placa
GRIS = colors.HexColor("#8A97A0")     # sitio sano
GRIS_CLARO = colors.HexColor("#D8E2E7")
TINTA = colors.HexColor("#16232E")

PASO = 28          # ancho por pieza
MARGEN = 16
ESCALA = 1.7       # puntos PDF por milímetro de sondaje
SEPARACION = 10    # hueco en la línea media


def _filas(tipo_paciente: str):
    if tipo_paciente == "nino":
        return FILA_SUPERIOR_NINO, FILA_INFERIOR_NINO
    return FILA_SUPERIOR_ADULTO, FILA_INFERIOR_ADULTO


def _cara(datos: dict, fdi: int, cara: str) -> dict:
    entrada = (datos or {}).get(str(fdi)) or {}
    return entrada.get(cara) or {}


def _valor(cara: dict, campo: str, i: int):
    lista = cara.get(campo)
    if isinstance(lista, list) and i < len(lista):
        return lista[i]
    return None


def _color_sitio(cara: dict, i: int):
    if _valor(cara, "sangrado", i):
        return ROJO
    if _valor(cara, "placa", i):
        return AZUL
    return GRIS


def _centro_x(i: int, por_hemiarco: int) -> float:
    return MARGEN + PASO / 2 + i * PASO + (SEPARACION if i >= por_hemiarco else 0)


def _dibujar_arcada(grupo, piezas, datos, por_hemiarco, y_cej, hacia_arriba):
    """
    Una arcada: línea amelocementaria, la curva de fondo de bolsa de cada cara
    y un punto por sitio. hacia_arriba dice de qué lado de la línea crece la
    profundidad (vestibular hacia afuera, palatina hacia adentro).
    """
    signo = 1 if hacia_arriba else -1
    ancho = _centro_x(len(piezas) - 1, por_hemiarco) + PASO / 2

    grupo.add(Line(MARGEN - 4, y_cej, ancho + 4, y_cej,
                   strokeColor=GRIS_CLARO, strokeWidth=0.7, strokeDashArray=[2, 2]))

    for cara, direccion in ((("vestibular"), signo), (("palatina"), -signo)):
        puntos = []
        for i, fdi in enumerate(piezas):
            datos_cara = _cara(datos, fdi, cara)
            cx = _centro_x(i, por_hemiarco)
            for s in SITIOS:
                x = cx + (s - 1) * (PASO / 3.4)
                mm = _valor(datos_cara, "sondaje", s) or 0
                y = y_cej + direccion * mm * ESCALA
                puntos.extend([x, y])
                grupo.add(Circle(x, y, 1.5, fillColor=_color_sitio(datos_cara, s),
                                 strokeColor=None))
        if puntos:
            grupo.add(PolyLine(puntos, strokeColor=ROJO, strokeWidth=0.7))

    return ancho


def dibujar_periodontograma(datos: dict, tipo_paciente: str) -> Drawing:
    """
    datos: el JSONB de "periodontogramas".datos, con la forma
           {"18": {"vestibular": {"sondaje":[3,4,3], "sangrado":[...], ...}, ...}}
    """
    fila_sup, fila_inf = _filas(tipo_paciente)
    por_hemiarco = len(fila_sup) // 2

    ancho = _centro_x(len(fila_sup) - 1, por_hemiarco) + PASO / 2 + MARGEN
    alto = 150

    y_cej_sup = 112
    y_cej_inf = 42
    y_numeros = 77

    dibujo = Drawing(ancho, alto)
    grupo = Group()

    _dibujar_arcada(grupo, fila_sup, datos, por_hemiarco, y_cej_sup, hacia_arriba=True)
    _dibujar_arcada(grupo, fila_inf, datos, por_hemiarco, y_cej_inf, hacia_arriba=False)

    # Números FDI en la franja del medio, igual que en la ficha web
    for piezas, dy in ((fila_sup, 4), (fila_inf, -6)):
        for i, fdi in enumerate(piezas):
            grupo.add(String(_centro_x(i, por_hemiarco), y_numeros + dy, str(fdi),
                             fontName="Helvetica", fontSize=5.2,
                             fillColor=colors.HexColor("#5C6D79"), textAnchor="middle"))

    # Rótulos de arcada
    for texto, y in (("SUPERIOR", alto - 8), ("INFERIOR", 6)):
        grupo.add(String(MARGEN - 4, y, texto, fontName="Helvetica-Bold", fontSize=5,
                         fillColor=colors.HexColor("#8A97A0")))

    dibujo.add(grupo)
    return dibujo


def leyenda_periodontograma():
    """Lista [(color_hex, etiqueta), ...] para pintar debajo del gráfico."""
    return [
        ("#D64545", "Sangrado al sondaje"),
        ("#1B6E8C", "Placa"),
        ("#8A97A0", "Sitio sano"),
    ]


def indices_periodontograma(registro: dict) -> list:
    """Los índices calculados, como pares (etiqueta, valor) para una tabla."""
    def num(campo, sufijo=""):
        valor = registro.get(campo)
        return f"{valor}{sufijo}" if valor is not None else "—"

    return [
        ("Índice de placa", num("indice_placa", "%")),
        ("Sangrado al sondaje", num("indice_sangrado", "%")),
        ("Profundidad media", num("media_sondaje", " mm")),
        ("Nivel de inserción medio", num("media_nic", " mm")),
        ("Sitios con supuración", num("sitios_supuracion")),
    ]
