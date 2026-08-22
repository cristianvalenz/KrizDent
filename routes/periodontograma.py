"""
Periodontograma: carta periodontal por cuadrantes, con 3 puntos de sondaje
por cara (distal / centro / mesial), encía queratinizada, encía adherida,
sangrado y placa — con dientes ilustrados en SVG, al estilo de una carta
periodontal clínica clásica.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services.supabase_client import sb

bp = Blueprint("periodontograma", __name__, url_prefix="/periodontograma")

FILA_SUPERIOR_ADULTO = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
FILA_INFERIOR_ADULTO = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
FILA_SUPERIOR_NINO = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65]
FILA_INFERIOR_NINO = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75]

CARAS = ["vestibular", "palatina"]
PUNTOS = ["ps3", "ps2", "ps1"]  # distal, centro, mesial


def _filas(paciente):
    es_nino = (paciente.get("tipo_paciente") or "adulto") == "nino"
    if es_nino:
        return FILA_SUPERIOR_NINO, FILA_INFERIOR_NINO
    return FILA_SUPERIOR_ADULTO, FILA_INFERIOR_ADULTO


@bp.route("/pacientes/<int:paciente_id>/nuevo", methods=["GET", "POST"])
def nuevo(paciente_id):
    paciente = _obtener_paciente(paciente_id)
    fila_superior, fila_inferior = _filas(paciente)
    piezas = fila_superior + fila_inferior

    if request.method == "POST":
        datos = {}
        total_caras = con_placa = con_sangrado = 0

        for p in piezas:
            caras_pieza = {}
            for cara in CARAS:
                sufijo = f"{p}_{cara}"
                puntos = {}
                for punto in PUNTOS:
                    valor = request.form.get(f"{punto}_{sufijo}")
                    if valor:
                        puntos[punto] = int(valor)
                eq = request.form.get(f"eq_{sufijo}") or None
                ead = request.form.get(f"ead_{sufijo}") or None
                sangrado = request.form.get(f"sangrado_{sufijo}") == "on"
                placa = request.form.get(f"placa_{sufijo}") == "on"

                total_caras += 1
                con_placa += placa
                con_sangrado += sangrado

                if puntos or eq or ead or sangrado or placa:
                    caras_pieza[cara] = {
                        "puntos": puntos,
                        "eq": int(eq) if eq else None,
                        "ead": int(ead) if ead else None,
                        "sangrado": sangrado, "placa": placa,
                    }
            if caras_pieza:
                datos[str(p)] = caras_pieza

        indice_placa = round(con_placa / total_caras * 100, 2) if total_caras else 0
        indice_sangrado = round(con_sangrado / total_caras * 100, 2) if total_caras else 0

        sb.table("periodontogramas").insert({
            "paciente_id": paciente_id,
            "indice_placa": indice_placa,
            "indice_sangrado": indice_sangrado,
            "sitios_supuracion": 0,
            "datos": datos,
            "notas": (request.form.get("notas") or "").strip() or None,
        }).execute()

        flash(f"Periodontograma guardado — IP {indice_placa}% · SAS {indice_sangrado}%.", "success")
        return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))

    return render_template(
        "periodontograma/formulario.html",
        paciente=paciente, fila_superior=fila_superior, fila_inferior=fila_inferior,
    )


ROJO = "#D64545"
AZUL = "#1B6E8C"
LINEA = "#8A97A0"


def _tipo_diente(fdi: int) -> str:
    pos = fdi % 10
    if pos in (6, 7, 8):
        return "molar"
    if pos in (4, 5):
        return "premolar"
    if pos == 3:
        return "canino"
    return "incisivo"


def _diente_svg(fdi: int, cx: float, y_base: float, direccion: int) -> dict:
    """
    Devuelve la geometría (corona ovalada + raíz(es)) de un diente simplificado.
    direccion=1 dibuja la corona en y_base y la(s) raíz(es) creciendo hacia abajo
    (fila bucal); direccion=-1 la dibuja espejada hacia arriba (fila palatina/lingual).
    """
    tipo = _tipo_diente(fdi)
    rx = 10 if tipo == "molar" else 8
    ry = 9
    raiz_largo = 30 if tipo == "molar" else 24
    y_corona = y_base
    y_raiz_fin = y_base + direccion * raiz_largo
    y_raiz_ini = y_base + direccion * ry

    if tipo == "molar":
        raices = [
            (cx - 5, y_raiz_ini, cx - 8, y_raiz_fin),
            (cx + 5, y_raiz_ini, cx + 8, y_raiz_fin),
        ]
    else:
        raices = [(cx, y_raiz_ini, cx, y_raiz_fin)]

    return {
        "fdi": fdi, "cx": cx, "cy": y_corona, "rx": rx, "ry": ry,
        "raices": raices,
    }


def _grafico_arcada(piezas, datos):
    """
    Precalcula un SVG de la arcada dividida en 2 cuadrantes, con la fila de
    dientes bucal arriba y palatina/lingual abajo (espejada), y las
    coordenadas de los puntos de sondaje (3 por cara) para dibujar la
    curva de profundidad.
    """
    paso = 34
    margen = 20
    hueco_cuadrante = 16
    mitad = len(piezas) // 2

    y_bucal = 46
    y_palatina = 108
    escala = 2.4  # px por mm de sondaje

    dientes_bucal, dientes_palatina, puntos_v, puntos_p = [], [], [], []
    x = margen
    for i, fdi in enumerate(piezas):
        if i == mitad:
            x += hueco_cuadrante
        dientes_bucal.append(_diente_svg(fdi, x, y_bucal, 1))
        dientes_palatina.append(_diente_svg(fdi, x, y_palatina, -1))

        cara_v = datos[fdi]["vestibular"]
        cara_p = datos[fdi]["palatina"]
        prof_v = max([v for v in cara_v.get("puntos", {}).values()] or [0])
        prof_p = max([v for v in cara_p.get("puntos", {}).values()] or [0])
        color_v = ROJO if cara_v.get("sangrado") else (AZUL if cara_v.get("placa") else LINEA)
        color_p = ROJO if cara_p.get("sangrado") else (AZUL if cara_p.get("placa") else LINEA)

        puntos_v.append({"x": x, "y": y_bucal - 16 - prof_v * escala, "color": color_v,
                          "valor": max(cara_v.get("puntos", {}).values(), default=None)})
        puntos_p.append({"x": x, "y": y_palatina + 16 + prof_p * escala, "color": color_p,
                          "valor": max(cara_p.get("puntos", {}).values(), default=None)})
        x += paso

    ancho = x - paso + margen
    polilinea_v = " ".join(f"{pt['x']},{pt['y']}" for pt in puntos_v)
    polilinea_p = " ".join(f"{pt['x']},{pt['y']}" for pt in puntos_p)

    return {
        "ancho": ancho, "alto": 140,
        "dientes_bucal": dientes_bucal, "dientes_palatina": dientes_palatina,
        "puntos_v": puntos_v, "puntos_p": puntos_p,
        "polilinea_v": polilinea_v, "polilinea_p": polilinea_p,
    }


@bp.route("/<int:periodontograma_id>")
def ver(periodontograma_id):
    fila = sb.table("periodontogramas").select("*").eq("id", periodontograma_id).limit(1).execute().data
    if not fila:
        abort(404)
    p = fila[0]
    paciente = _obtener_paciente(p["paciente_id"])
    fila_superior, fila_inferior = _filas(paciente)

    vacio = {"puntos": {}, "eq": None, "ead": None, "sangrado": False, "placa": False}
    datos_completos = {}
    for p_fdi in fila_superior + fila_inferior:
        entrada = (p["datos"] or {}).get(str(p_fdi), {})
        datos_completos[p_fdi] = {cara: entrada.get(cara, dict(vacio)) for cara in CARAS}

    return render_template(
        "periodontograma/ver.html",
        paciente=paciente, p=p, fila_superior=fila_superior, fila_inferior=fila_inferior,
        datos=datos_completos,
        grafico_superior=_grafico_arcada(fila_superior, datos_completos),
        grafico_inferior=_grafico_arcada(fila_inferior, datos_completos),
    )


@bp.route("/<int:periodontograma_id>/eliminar", methods=["POST"])
def eliminar(periodontograma_id):
    fila = sb.table("periodontogramas").select("paciente_id").eq("id", periodontograma_id).limit(1).execute().data
    if not fila:
        abort(404)
    sb.table("periodontogramas").delete().eq("id", periodontograma_id).execute()
    flash("Periodontograma eliminado.", "info")
    return redirect(url_for("pacientes.detalle", paciente_id=fila[0]["paciente_id"]))


def _obtener_paciente(paciente_id: int) -> dict:
    resp = sb.table("pacientes").select("*").eq("id", paciente_id).limit(1).execute()
    if not resp.data:
        abort(404)
    return resp.data[0]
