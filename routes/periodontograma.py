"""
Periodontograma: carta periodontal por cara (vestibular / palatina-lingual).

Captura, por pieza y por cara, sondaje (mm), margen gingival (mm), sangrado y
placa — lo mismo que mide una carta periodontal real, aunque la vista no
dibuja la curva exacta pixel a pixel de un software clínico. Los índices
%IP (placa) y %SAS (sangrado) se calculan solos sobre el total de caras.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services.supabase_client import sb

bp = Blueprint("periodontograma", __name__, url_prefix="/periodontograma")

FILA_SUPERIOR_ADULTO = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
FILA_INFERIOR_ADULTO = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
FILA_SUPERIOR_NINO = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65]
FILA_INFERIOR_NINO = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75]

CARAS = ["vestibular", "palatina"]


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
        total_caras = con_placa = con_sangrado = con_supuracion = 0

        for p in piezas:
            caras_pieza = {}
            for cara in CARAS:
                sufijo = f"{p}_{cara}"
                sondaje = request.form.get(f"sondaje_{sufijo}") or None
                margen = request.form.get(f"margen_{sufijo}") or None
                sangrado = request.form.get(f"sangrado_{sufijo}") == "on"
                placa = request.form.get(f"placa_{sufijo}") == "on"
                supuracion = request.form.get(f"supuracion_{sufijo}") == "on"

                total_caras += 1
                con_placa += placa
                con_sangrado += sangrado
                con_supuracion += supuracion

                if sondaje or margen or sangrado or placa or supuracion:
                    caras_pieza[cara] = {
                        "sondaje": int(sondaje) if sondaje else None,
                        "margen": int(margen) if margen else None,
                        "sangrado": sangrado, "placa": placa, "supuracion": supuracion,
                    }
            if caras_pieza:
                datos[str(p)] = caras_pieza

        indice_placa = round(con_placa / total_caras * 100, 2) if total_caras else 0
        indice_sangrado = round(con_sangrado / total_caras * 100, 2) if total_caras else 0

        sb.table("periodontogramas").insert({
            "paciente_id": paciente_id,
            "indice_placa": indice_placa,
            "indice_sangrado": indice_sangrado,
            "sitios_supuracion": con_supuracion,
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
GRIS = "#C6D0D6"


def _color_cara(cara: dict) -> str:
    if cara.get("sangrado"):
        return ROJO
    if cara.get("placa"):
        return AZUL
    return GRIS


def _grafico_arcada(piezas, datos):
    """
    Precalcula las coordenadas de un SVG simple: una polilínea de sondaje por
    cara (vestibular arriba de la línea media, palatina/lingual abajo) con
    un punto de color en cada pieza — rojo si sangra, azul si tiene placa.
    """
    paso = 40
    margen = 24
    ancho = margen * 2 + paso * max(len(piezas) - 1, 0)
    medio_y = 70
    escala = 3   # px por mm de sondaje

    puntos = []
    for i, fdi in enumerate(piezas):
        x = margen + i * paso
        cara_v = datos[fdi]["vestibular"]
        cara_p = datos[fdi]["palatina"]
        sondaje_v = cara_v.get("sondaje") or 0
        sondaje_p = cara_p.get("sondaje") or 0
        puntos.append({
            "fdi": fdi, "x": x,
            "yv": medio_y - sondaje_v * escala, "yp": medio_y + sondaje_p * escala,
            "colorv": _color_cara(cara_v), "colorp": _color_cara(cara_p),
            "sondajev": cara_v.get("sondaje"), "sondajep": cara_p.get("sondaje"),
        })

    polilinea_v = " ".join(f"{pt['x']},{pt['yv']}" for pt in puntos)
    polilinea_p = " ".join(f"{pt['x']},{pt['yp']}" for pt in puntos)

    return {"ancho": ancho, "alto": 140, "medio_y": medio_y, "puntos": puntos,
            "polilinea_v": polilinea_v, "polilinea_p": polilinea_p}


@bp.route("/<int:periodontograma_id>")
def ver(periodontograma_id):
    fila = sb.table("periodontogramas").select("*").eq("id", periodontograma_id).limit(1).execute().data
    if not fila:
        abort(404)
    p = fila[0]
    paciente = _obtener_paciente(p["paciente_id"])
    fila_superior, fila_inferior = _filas(paciente)

    # Para el gráfico: cada pieza necesita datos de las 2 caras (aunque estén
    # vacías) para que las columnas no se desalineen en la plantilla.
    datos_completos = {}
    for p_fdi in fila_superior + fila_inferior:
        entrada = (p["datos"] or {}).get(str(p_fdi), {})
        datos_completos[p_fdi] = {
            cara: entrada.get(cara, {"sondaje": None, "margen": None, "sangrado": False, "placa": False, "supuracion": False})
            for cara in CARAS
        }

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
