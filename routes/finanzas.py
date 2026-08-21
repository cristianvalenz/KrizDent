"""Presupuestos (tratamientos con costo) y pagos por paciente."""

from flask import Blueprint, abort, flash, redirect, request, url_for

from services.constantes import ESTADOS_TRATAMIENTO, METODOS_PAGO
from services.supabase_client import sb

bp = Blueprint("finanzas", __name__)


@bp.route("/pacientes/<int:paciente_id>/tratamientos", methods=["POST"])
def nuevo_tratamiento(paciente_id):
    descripcion = (request.form.get("descripcion") or "").strip()
    try:
        costo = float(request.form.get("costo") or 0)
    except ValueError:
        costo = -1

    if not descripcion or costo < 0:
        flash("El tratamiento necesita descripción y un costo válido.", "danger")
        return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))

    sb.table("tratamientos").insert({
        "paciente_id": paciente_id,
        "descripcion": descripcion,
        "costo": costo,
        "estado": request.form.get("estado") or "pendiente",
    }).execute()

    flash("Tratamiento agregado al presupuesto.", "success")
    return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))


@bp.route("/tratamientos/<int:tratamiento_id>/estado", methods=["POST"])
def cambiar_estado_tratamiento(tratamiento_id):
    nuevo = request.form.get("estado")
    if nuevo not in ESTADOS_TRATAMIENTO:
        abort(400)
    fila = sb.table("tratamientos").select("paciente_id").eq("id", tratamiento_id).limit(1).execute().data
    if not fila:
        abort(404)
    sb.table("tratamientos").update({"estado": nuevo}).eq("id", tratamiento_id).execute()
    return redirect(url_for("pacientes.detalle", paciente_id=fila[0]["paciente_id"]))


@bp.route("/tratamientos/<int:tratamiento_id>/eliminar", methods=["POST"])
def eliminar_tratamiento(tratamiento_id):
    fila = sb.table("tratamientos").select("paciente_id").eq("id", tratamiento_id).limit(1).execute().data
    if not fila:
        abort(404)
    sb.table("tratamientos").delete().eq("id", tratamiento_id).execute()
    flash("Tratamiento eliminado del presupuesto.", "info")
    return redirect(url_for("pacientes.detalle", paciente_id=fila[0]["paciente_id"]))


@bp.route("/pacientes/<int:paciente_id>/pagos", methods=["POST"])
def nuevo_pago(paciente_id):
    try:
        monto = float(request.form.get("monto") or 0)
    except ValueError:
        monto = -1

    if monto <= 0:
        flash("El monto del pago tiene que ser mayor a cero.", "danger")
        return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))

    tratamiento_id = request.form.get("tratamiento_id") or None

    sb.table("pagos").insert({
        "paciente_id": paciente_id,
        "tratamiento_id": int(tratamiento_id) if tratamiento_id else None,
        "monto": monto,
        "metodo": request.form.get("metodo") if request.form.get("metodo") in METODOS_PAGO else "efectivo",
        "notas": (request.form.get("notas") or "").strip() or None,
    }).execute()

    flash(f"Pago de S/ {monto:.2f} registrado.", "success")
    return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))


@bp.route("/pagos/<int:pago_id>/eliminar", methods=["POST"])
def eliminar_pago(pago_id):
    fila = sb.table("pagos").select("paciente_id").eq("id", pago_id).limit(1).execute().data
    if not fila:
        abort(404)
    sb.table("pagos").delete().eq("id", pago_id).execute()
    flash("Pago eliminado.", "info")
    return redirect(url_for("pacientes.detalle", paciente_id=fila[0]["paciente_id"]))
