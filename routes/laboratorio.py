"""Seguimiento de trabajos enviados al laboratorio dental (coronas, prótesis, etc.)."""

from flask import Blueprint, abort, flash, redirect, request, url_for

from services.constantes import ESTADOS_LABORATORIO
from services.auth import dele, ins, sel, upd


bp = Blueprint("laboratorio", __name__, url_prefix="/laboratorio")


@bp.route("/pacientes/<int:paciente_id>/nuevo", methods=["POST"])
def nuevo(paciente_id):
    descripcion = (request.form.get("descripcion") or "").strip()
    if not descripcion:
        flash("Describe qué se envió al laboratorio.", "danger")
        return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))

    ins("trabajos_laboratorio", {
        "paciente_id": paciente_id,
        "descripcion": descripcion,
        "laboratorio": (request.form.get("laboratorio") or "").strip() or None,
        "fecha_estimada": request.form.get("fecha_estimada") or None,
        "notas": (request.form.get("notas") or "").strip() or None,
    }).execute()

    flash("Trabajo de laboratorio registrado.", "success")
    return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))


@bp.route("/<int:trabajo_id>/estado", methods=["POST"])
def cambiar_estado(trabajo_id):
    nuevo_estado = request.form.get("estado")
    if nuevo_estado not in ESTADOS_LABORATORIO:
        abort(400)

    fila = sel("trabajos_laboratorio", "paciente_id").eq("id", trabajo_id).limit(1).execute().data
    if not fila:
        abort(404)

    datos = {"estado": nuevo_estado}
    if nuevo_estado == "entregado":
        from datetime import date
        datos["fecha_recibido"] = date.today().isoformat()

    upd("trabajos_laboratorio", datos).eq("id", trabajo_id).execute()
    return redirect(url_for("pacientes.detalle", paciente_id=fila[0]["paciente_id"]))


@bp.route("/<int:trabajo_id>/eliminar", methods=["POST"])
def eliminar(trabajo_id):
    fila = sel("trabajos_laboratorio", "paciente_id").eq("id", trabajo_id).limit(1).execute().data
    if not fila:
        abort(404)
    dele("trabajos_laboratorio").eq("id", trabajo_id).execute()
    flash("Registro de laboratorio eliminado.", "info")
    return redirect(url_for("pacientes.detalle", paciente_id=fila[0]["paciente_id"]))
