"""Agenda: registro de citas, listado por día/semana y cambio de estado."""

from datetime import date, datetime, timedelta

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)

from services.constantes import ESTADOS_CITA
from services.supabase_client import sb

bp = Blueprint("citas", __name__, url_prefix="/citas")


@bp.route("/")
def lista():
    """
    Agenda agrupada por día.
    Filtros por querystring: ?desde=2026-03-01&hasta=2026-03-31&estado=pendiente
    Por defecto muestra desde hoy hasta 14 días adelante.
    """
    hoy = datetime.now().date()
    desde = request.args.get("desde") or hoy.isoformat()
    hasta = request.args.get("hasta") or (hoy + timedelta(days=14)).isoformat()
    estado = request.args.get("estado") or ""

    consulta = (
        sb.table("citas")
        .select("*, pacientes(id, nombre, telefono)")
        .gte("fecha_hora", f"{desde}T00:00:00")
        .lte("fecha_hora", f"{hasta}T23:59:59")
    )
    if estado in ESTADOS_CITA:
        consulta = consulta.eq("estado", estado)

    citas = consulta.order("fecha_hora").execute().data or []

    # Agrupamos en Python (no en SQL) porque el volumen es pequeño
    # y así la plantilla queda simple: {"2026-03-14": [cita, cita], ...}
    por_dia = {}
    for c in citas:
        clave = (c["fecha_hora"] or "")[:10]
        por_dia.setdefault(clave, []).append(c)

    return render_template(
        "citas/lista.html",
        por_dia=por_dia,
        total=len(citas),
        desde=desde,
        hasta=hasta,
        estado=estado,
        estados=ESTADOS_CITA,
    )


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    if request.method == "POST":
        paciente_id = request.form.get("paciente_id")
        fecha_hora = request.form.get("fecha_hora")

        if not paciente_id or not fecha_hora:
            flash("Elige un paciente y una fecha para la cita.", "danger")
            return redirect(url_for("citas.nueva"))

        sb.table("citas").insert({
            "paciente_id": int(paciente_id),
            "fecha_hora": fecha_hora,           # '2026-03-14T09:30' del input datetime-local
            "duracion_min": int(request.form.get("duracion_min") or 30),
            "motivo": (request.form.get("motivo") or "").strip() or None,
            "estado": request.form.get("estado") or "pendiente",
            "notas": (request.form.get("notas") or "").strip() or None,
        }).execute()

        flash("Cita agendada.", "success")
        return redirect(url_for("citas.lista"))

    return render_template(
        "citas/formulario.html",
        cita={"paciente_id": request.args.get("paciente_id", type=int)},
        pacientes=_pacientes_activos(),
        estados=ESTADOS_CITA,
        modo="nueva",
    )


@bp.route("/<int:cita_id>/editar", methods=["GET", "POST"])
def editar(cita_id):
    cita = _obtener_cita(cita_id)

    if request.method == "POST":
        sb.table("citas").update({
            "paciente_id": int(request.form["paciente_id"]),
            "fecha_hora": request.form["fecha_hora"],
            "duracion_min": int(request.form.get("duracion_min") or 30),
            "motivo": (request.form.get("motivo") or "").strip() or None,
            "estado": request.form.get("estado") or "pendiente",
            "notas": (request.form.get("notas") or "").strip() or None,
        }).eq("id", cita_id).execute()

        flash("Cita actualizada.", "success")
        return redirect(url_for("citas.lista"))

    return render_template(
        "citas/formulario.html",
        cita=cita,
        pacientes=_pacientes_activos(),
        estados=ESTADOS_CITA,
        modo="editar",
    )


@bp.route("/<int:cita_id>/estado", methods=["POST"])
def cambiar_estado(cita_id):
    """Cambio rápido de estado desde los botones del listado."""
    nuevo = request.form.get("estado")
    if nuevo not in ESTADOS_CITA:
        flash("Ese estado no existe.", "danger")
        return redirect(request.referrer or url_for("citas.lista"))

    sb.table("citas").update({"estado": nuevo}).eq("id", cita_id).execute()
    flash(f"Cita marcada como {ESTADOS_CITA[nuevo]['etiqueta'].lower()}.", "success")
    return redirect(request.referrer or url_for("citas.lista"))


@bp.route("/<int:cita_id>/eliminar", methods=["POST"])
def eliminar(cita_id):
    sb.table("citas").delete().eq("id", cita_id).execute()
    flash("Cita eliminada de la agenda.", "info")
    return redirect(request.referrer or url_for("citas.lista"))


@bp.route("/<int:cita_id>/recordatorio", methods=["POST"])
def marcar_recordatorio(cita_id):
    """
    No hay integración con una API de WhatsApp de pago: el botón abre un
    enlace wa.me con el mensaje ya escrito (el navegador abre WhatsApp Web
    o la app), y esta llamada solo anota que ya se avisó, para no repetir.
    """
    sb.table("citas").update({"recordatorio_enviado": True}).eq("id", cita_id).execute()
    return ("", 204)


@bp.route("/calendario")
def calendario():
    """Vista mensual. ?mes=2026-03, si no se indica usa el mes actual."""
    hoy = datetime.now().date()
    mes_param = request.args.get("mes")
    try:
        anio, mes = (int(x) for x in mes_param.split("-")) if mes_param else (hoy.year, hoy.month)
    except ValueError:
        anio, mes = hoy.year, hoy.month

    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio + (mes == 12), (mes % 12) + 1, 1) - timedelta(days=1)

    citas = (
        sb.table("citas").select("*, pacientes(id, nombre)")
        .gte("fecha_hora", f"{primer_dia.isoformat()}T00:00:00")
        .lte("fecha_hora", f"{ultimo_dia.isoformat()}T23:59:59")
        .order("fecha_hora").execute().data or []
    )
    por_dia = {}
    for c in citas:
        por_dia.setdefault((c["fecha_hora"] or "")[:10], []).append(c)

    # Cuadrícula de semanas completas (lunes a domingo) para dibujar el mes.
    primer_lunes = primer_dia - timedelta(days=primer_dia.weekday())
    ultimo_domingo = ultimo_dia + timedelta(days=6 - ultimo_dia.weekday())
    semanas, semana_actual, d = [], [], primer_lunes
    while d <= ultimo_domingo:
        semana_actual.append(d)
        if len(semana_actual) == 7:
            semanas.append(semana_actual)
            semana_actual = []
        d += timedelta(days=1)

    mes_anterior = (primer_dia - timedelta(days=1)).strftime("%Y-%m")
    mes_siguiente = (ultimo_dia + timedelta(days=1)).strftime("%Y-%m")

    nombres_mes = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                   "agosto", "setiembre", "octubre", "noviembre", "diciembre"]

    return render_template(
        "citas/calendario.html",
        semanas=semanas, por_dia=por_dia, mes_actual=primer_dia,
        mes_etiqueta=f"{nombres_mes[mes - 1]} {anio}",
        mes_anterior=mes_anterior, mes_siguiente=mes_siguiente, hoy=hoy,
    )


# --- Utilidades internas ---------------------------------------------------

def _pacientes_activos():
    return (
        sb.table("pacientes").select("id, nombre")
        .eq("activo", True).order("nombre").execute().data or []
    )


def _obtener_cita(cita_id: int) -> dict:
    resp = sb.table("citas").select("*").eq("id", cita_id).limit(1).execute()
    if not resp.data:
        abort(404)
    return resp.data[0]
