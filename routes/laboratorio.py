"""Seguimiento de trabajos enviados al laboratorio dental (coronas, prótesis, etc.)."""

from flask import Blueprint, abort, flash, redirect, request, url_for

from services.constantes import ESTADOS_LABORATORIO
from services.supabase_client import sb

bp = Blueprint("laboratorio", __name__, url_prefix="/laboratorio")


@bp.route("/pacientes/<int:paciente_id>/nuevo", methods=["POST"])
def nuevo(paciente_id):
    descripcion = (request.form.get("descripcion") or "").strip()
    if not descripcion:
        flash("Describe qué se envió al laboratorio.", "danger")
        return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))

    sb.table("trabajos_laboratorio").insert({
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

    fila = sb.table("trabajos_laboratorio").select("paciente_id").eq("id", trabajo_id).limit(1).execute().data
    if not fila:
        abort(404)

    datos = {"estado": nuevo_estado}
    if nuevo_estado == "entregado":
        from datetime import date
        datos["fecha_recibido"] = date.today().isoformat()

    sb.table("trabajos_laboratorio").update(datos).eq("id", trabajo_id).execute()
    return redirect(url_for("pacientes.detalle", paciente_id=fila[0]["paciente_id"]))


@bp.route("/<int:trabajo_id>/eliminar", methods=["POST"])
def eliminar(trabajo_id):
    fila = sb.table("trabajos_laboratorio").select("paciente_id").eq("id", trabajo_id).limit(1).execute().data
    if not fila:
        abort(404)
    sb.table("trabajos_laboratorio").delete().eq("id", trabajo_id).execute()
    flash("Registro de laboratorio eliminado.", "info")
    return redirect(url_for("pacientes.detalle", paciente_id=fila[0]["paciente_id"]))
