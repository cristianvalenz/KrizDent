"""Presupuestos (tratamientos con costo) y pagos por paciente."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services.constantes import ESTADOS_TRATAMIENTO, METODOS_PAGO
from services.supabase_client import sb

bp = Blueprint("finanzas", __name__)


@bp.route("/presupuestos")
def lista():
    """
    Listado global de presupuestos de todos los pacientes, con filtros y los
    mismos 3 totales que Dentalink: presupuestado, cobrado, falta por cobrar.
    """
    paciente_q = (request.args.get("paciente") or "").strip()
    estado = request.args.get("estado") or ""
    profesional_id = request.args.get("profesional_id") or ""

    consulta = (
        sb.table("tratamientos")
        .select("*, pacientes(id, nombre), profesionales(id, nombre)")
    )
    if estado in ESTADOS_TRATAMIENTO:
        consulta = consulta.eq("estado", estado)
    if profesional_id:
        consulta = consulta.eq("profesional_id", int(profesional_id))

    tratamientos = consulta.order("fecha", desc=True).execute().data or []

    if paciente_q:
        q_low = paciente_q.lower()
        tratamientos = [t for t in tratamientos if q_low in (t.get("pacientes") or {}).get("nombre", "").lower()]

    # El "cobrado" de cada línea = pagos asociados a ese tratamiento específico.
    ids_tratamiento = [t["id"] for t in tratamientos]
    pagos_por_tratamiento = {}
    if ids_tratamiento:
        pagos = (
            sb.table("pagos").select("tratamiento_id, monto")
            .in_("tratamiento_id", ids_tratamiento).execute().data or []
        )
        for p in pagos:
            if p["tratamiento_id"]:
                pagos_por_tratamiento[p["tratamiento_id"]] = pagos_por_tratamiento.get(p["tratamiento_id"], 0) + float(p["monto"])

    for t in tratamientos:
        t["cobrado"] = round(pagos_por_tratamiento.get(t["id"], 0), 2)
        t["falta"] = round(float(t["costo"]) - t["cobrado"], 2)

    total_presupuestado = sum(float(t["costo"]) for t in tratamientos if t["estado"] != "cancelado")
    total_cobrado = sum(t["cobrado"] for t in tratamientos)
    total_falta = round(total_presupuestado - total_cobrado, 2)

    profesionales = sb.table("profesionales").select("id, nombre").eq("activo", True).order("nombre").execute().data or []

    return render_template(
        "finanzas/lista.html",
        tratamientos=tratamientos, paciente_q=paciente_q, estado=estado, profesional_id=profesional_id,
        estados_tratamiento=ESTADOS_TRATAMIENTO, profesionales=profesionales,
        total_presupuestado=total_presupuestado, total_cobrado=total_cobrado, total_falta=total_falta,
    )


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

    profesional_id = request.form.get("profesional_id") or None
    pieza = request.form.get("pieza") or None

    sb.table("tratamientos").insert({
        "paciente_id": paciente_id,
        "descripcion": descripcion,
        "costo": costo,
        "estado": request.form.get("estado") or "pendiente",
        "profesional_id": int(profesional_id) if profesional_id else None,
        "pieza": int(pieza) if pieza else None,
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
