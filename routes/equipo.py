"""
Zona del titular de la clínica: su equipo y sus reportes al administrador.

El titular NO crea cuentas — eso lo hace solo el administrador de la
plataforma, que es quien cobra la mensualidad y controla cuántos usuarios
tiene cada plan. Lo que sí puede es darles mantenimiento: corregir el
nombre, el correo, repartir módulos, reiniciar una clave olvidada o
desactivar a quien ya no trabaja ahí.

Todo se limita a los usuarios de SU clínica: las consultas filtran por
clinica_id y además se verifica antes de tocar cada fila.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services.auth import (clinica_actual, clinica_id, hashear,
                           requiere_titular, usuario_actual)
from services.constantes import ESTADOS_REPORTE, MODULOS, TIPOS_REPORTE
from services.supabase_client import sb

bp = Blueprint("equipo", __name__, url_prefix="/equipo")


def _mio(usuario_id: int) -> dict:
    """
    Trae un usuario solo si es de la clínica en sesión. Sin esto, un titular
    podría editar la cuenta de otra clínica cambiando el id de la URL.
    """
    filas = (
        sb.table("usuarios").select("*")
        .eq("id", usuario_id).eq("clinica_id", clinica_id())
        .limit(1).execute().data
    )
    if not filas:
        abort(404)
    return filas[0]


def _modulos_del_plan() -> list:
    """Lo que la clínica contrató: el titular no puede dar más que eso."""
    clinica = clinica_actual() or {}
    return [m for m in (clinica.get("modulos") or []) if m in MODULOS]


@bp.route("/")
@requiere_titular
def lista():
    usuarios = (
        sb.table("usuarios").select("*")
        .eq("clinica_id", clinica_id()).order("nombre").execute().data or []
    )
    return render_template(
        "equipo/lista.html",
        usuarios=usuarios,
        modulos=MODULOS,
        modulos_plan=_modulos_del_plan(),
        yo=usuario_actual(),
    )


@bp.route("/<int:usuario_id>/guardar", methods=["POST"])
@requiere_titular
def guardar(usuario_id):
    usuario = _mio(usuario_id)
    plan = _modulos_del_plan()
    email = (request.form.get("email") or "").strip().lower() or None

    if email:
        ocupado = (
            sb.table("usuarios").select("id").ilike("email", email)
            .neq("id", usuario_id).limit(1).execute().data
        )
        if ocupado:
            flash(f"Otra cuenta ya usa el correo {email}.", "danger")
            return redirect(url_for("equipo.lista"))

    cambios = {
        "nombre": (request.form.get("nombre") or "").strip() or usuario["nombre"],
        "email": email,
    }

    # El titular no se puede desactivar a sí mismo ni bajarse de rol: quedaría
    # la clínica sin quien administre a su gente.
    if usuario["id"] != (usuario_actual() or {}).get("id"):
        cambios["activo"] = request.form.get("activo") == "on"

    if usuario["rol"] != "dueno":
        # Solo módulos del plan: no puede regalar lo que su clínica no contrató.
        pedidos = set(request.form.getlist("modulos"))
        cambios["modulos"] = [m for m in plan if m in pedidos]

    sb.table("usuarios").update(cambios).eq("id", usuario_id).execute()
    flash(f"«{usuario['usuario']}» actualizado.", "success")
    return redirect(url_for("equipo.lista"))


@bp.route("/<int:usuario_id>/clave", methods=["POST"])
@requiere_titular
def clave(usuario_id):
    usuario = _mio(usuario_id)
    nueva = (request.form.get("clave") or "").strip()

    if len(nueva) < 5:
        flash("La contraseña debe tener al menos 5 caracteres.", "danger")
    else:
        sb.table("usuarios").update(
            {"password_hash": hashear(nueva)}
        ).eq("id", usuario_id).execute()
        flash(f"Contraseña de «{usuario['usuario']}» cambiada a: {nueva}", "success")

    return redirect(url_for("equipo.lista"))


# ---------------------------------------------------------------------
# Reportes hacia el administrador de la plataforma
# ---------------------------------------------------------------------

@bp.route("/reportes", methods=["GET", "POST"])
def reportes():
    """
    Cualquier usuario de la clínica puede avisar de una falla; no hace falta
    ser titular para que algo roto se pueda reportar.
    """
    if request.method == "POST":
        asunto = (request.form.get("asunto") or "").strip()
        detalle = (request.form.get("detalle") or "").strip()
        tipo = request.form.get("tipo") if request.form.get("tipo") in TIPOS_REPORTE else "falla"

        if not asunto or not detalle:
            flash("El asunto y el detalle son obligatorios.", "danger")
        else:
            sb.table("reportes_plataforma").insert({
                "clinica_id": clinica_id(),
                "usuario_id": (usuario_actual() or {}).get("id"),
                "asunto": asunto,
                "detalle": detalle,
                "tipo": tipo,
            }).execute()
            flash("Reporte enviado. El administrador lo verá en su panel.", "success")
        return redirect(url_for("equipo.reportes"))

    mios = (
        sb.table("reportes_plataforma").select("*")
        .eq("clinica_id", clinica_id()).order("creado_en", desc=True)
        .execute().data or []
    )
    return render_template("equipo/reportes.html", reportes=mios,
                           tipos=TIPOS_REPORTE, estados=ESTADOS_REPORTE)
