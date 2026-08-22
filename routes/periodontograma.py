"""
Periodontograma: carta periodontal simplificada.

La versión completa de un periodontograma clínico mide 6 sitios por pieza
(profundidad de sondaje, margen gingival, sangrado, placa, supuración) y se
dibuja como una curva — replicarla pixel a pixel es un proyecto en sí mismo.
Esta versión captura lo mismo por pieza (no por sitio) y calcula los mismos
dos índices que de verdad se usan para el seguimiento clínico: %IP (placa)
y %SAS (sangrado al sondaje).
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services.supabase_client import sb

bp = Blueprint("periodontograma", __name__, url_prefix="/periodontograma")

FILA_SUPERIOR_ADULTO = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
FILA_INFERIOR_ADULTO = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
FILA_SUPERIOR_NINO = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65]
FILA_INFERIOR_NINO = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75]


@bp.route("/pacientes/<int:paciente_id>/nuevo", methods=["GET", "POST"])
def nuevo(paciente_id):
    paciente = _obtener_paciente(paciente_id)
    es_nino = (paciente.get("tipo_paciente") or "adulto") == "nino"
    piezas = (FILA_SUPERIOR_NINO + FILA_INFERIOR_NINO) if es_nino else (FILA_SUPERIOR_ADULTO + FILA_INFERIOR_ADULTO)

    if request.method == "POST":
        datos = {}
        con_placa = con_sangrado = con_supuracion = 0
        for p in piezas:
            placa = request.form.get(f"placa_{p}") == "on"
            sangrado = request.form.get(f"sangrado_{p}") == "on"
            supuracion = request.form.get(f"supuracion_{p}") == "on"
            sondaje = request.form.get(f"sondaje_{p}") or None
            if placa or sangrado or supuracion or sondaje:
                datos[str(p)] = {
                    "placa": placa, "sangrado": sangrado, "supuracion": supuracion,
                    "sondaje": int(sondaje) if sondaje else None,
                }
            con_placa += placa
            con_sangrado += sangrado
            con_supuracion += supuracion

        total = len(piezas)
        indice_placa = round(con_placa / total * 100, 2) if total else 0
        indice_sangrado = round(con_sangrado / total * 100, 2) if total else 0

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
        paciente=paciente, fila_superior=FILA_SUPERIOR_NINO if es_nino else FILA_SUPERIOR_ADULTO,
        fila_inferior=FILA_INFERIOR_NINO if es_nino else FILA_INFERIOR_ADULTO,
    )


@bp.route("/<int:periodontograma_id>")
def ver(periodontograma_id):
    fila = sb.table("periodontogramas").select("*").eq("id", periodontograma_id).limit(1).execute().data
    if not fila:
        abort(404)
    p = fila[0]
    paciente = _obtener_paciente(p["paciente_id"])
    es_nino = (paciente.get("tipo_paciente") or "adulto") == "nino"
    return render_template(
        "periodontograma/ver.html",
        paciente=paciente, p=p,
        fila_superior=FILA_SUPERIOR_NINO if es_nino else FILA_SUPERIOR_ADULTO,
        fila_inferior=FILA_INFERIOR_NINO if es_nino else FILA_INFERIOR_ADULTO,
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
