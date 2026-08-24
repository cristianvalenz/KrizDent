"""
Panel del administrador de la plataforma.

Aquí se dan de alta las clínicas que alquilan el sistema, se decide qué
módulos incluye su plan, hasta cuándo está pagada la mensualidad y quiénes
son sus usuarios.

A propósito NO hay ninguna consulta a pacientes, citas ni historias: el
administrador de la plataforma administra cuentas, no datos clínicos.
"""

import re
import unicodedata
from datetime import date, datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services.auth import hashear, requiere_superadmin, usuario_actual
from services.constantes import (ESTADOS_REPORTE, MODULOS, ROLES, TIPOS_REPORTE)
from services.documentos import validar_ruc
from services.storage import ErrorSubida, borrar_imagen, subir_logo
from services.supabase_client import sb


bp = Blueprint("admin", __name__, url_prefix="/admin")

CLAVE_POR_DEFECTO = "12345"


def _slug(texto: str) -> str:
    """Nombre → identificador corto, sin tildes ni espacios."""
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-") or "clinica"


def _slug_libre(base: str) -> str:
    slug = base
    n = 2
    while sb.table("clinicas").select("id").eq("slug", slug).limit(1).execute().data:
        slug = f"{base}-{n}"
        n += 1
    return slug


def _modulos_del_form() -> list:
    return [m for m in request.form.getlist("modulos") if m in MODULOS]


def _usuario_libre(acceso: str, excluir_id=None) -> bool:
    consulta = sb.table("usuarios").select("id").ilike("usuario", acceso)
    if excluir_id:
        consulta = consulta.neq("id", excluir_id)
    return not consulta.limit(1).execute().data


def _ocupado(acceso: str, email, excluir_id=None):
    """
    Devuelve el mensaje de choque, o None si usuario y correo están libres.
    El usuario se compara sin distinguir mayúsculas, igual que al entrar.
    """
    if not _usuario_libre(acceso, excluir_id):
        # El usuario es libre a propósito (puede ser un cargo, una sede...),
        # así que en vez de imponer un formato se propone el siguiente libre.
        for n in range(2, 12):
            alternativa = f"{acceso}{n}"
            if _usuario_libre(alternativa, excluir_id):
                return (f"Ya existe una cuenta con el usuario «{acceso}». "
                        f"Puedes usar «{alternativa}» u otro que prefieras.")
        return f"Ya existe una cuenta con el usuario «{acceso}»."

    if email:
        consulta = sb.table("usuarios").select("id").ilike("email", email)
        if excluir_id:
            consulta = consulta.neq("id", excluir_id)
        if consulta.limit(1).execute().data:
            return f"Ya existe una cuenta con el correo {email}."
    return None


def _fecha_o_none(valor: str):
    valor = (valor or "").strip()
    return valor or None


def _sumar_un_mes(desde: date) -> date:
    """Misma fecha del mes siguiente; si no existe (31), cae al último día."""
    anio = desde.year + (1 if desde.month == 12 else 0)
    mes = 1 if desde.month == 12 else desde.month + 1
    dia = desde.day
    while dia > 28:
        try:
            return date(anio, mes, dia)
        except ValueError:
            dia -= 1
    return date(anio, mes, dia)


# ---------------------------------------------------------------------
# Clínicas
# ---------------------------------------------------------------------

@bp.route("/")
@bp.route("/clinicas")
@requiere_superadmin
def clinicas():
    filas = sb.table("clinicas").select("*").order("nombre").execute().data or []
    usuarios = sb.table("usuarios").select("clinica_id, activo").execute().data or []

    conteo = {}
    for u in usuarios:
        if u["clinica_id"]:
            conteo[u["clinica_id"]] = conteo.get(u["clinica_id"], 0) + 1

    hoy = date.today()
    for c in filas:
        c["usuarios"] = conteo.get(c["id"], 0)
        vence = c.get("vence_el")
        c["vencida"] = bool(vence and date.fromisoformat(vence) < hoy)
        c["dias_restantes"] = (date.fromisoformat(vence) - hoy).days if vence else None

    return render_template("admin/clinicas.html", clinicas=filas, modulos=MODULOS, hoy=hoy)


@bp.route("/clinicas/nueva", methods=["POST"])
@requiere_superadmin
def nueva_clinica():
    nombre = (request.form.get("nombre") or "").strip()
    if not nombre:
        flash("El nombre de la clínica es obligatorio.", "danger")
        return redirect(url_for("admin.clinicas"))

    ruc, error_ruc = validar_ruc(request.form.get("ruc"))
    if error_ruc:
        flash(error_ruc, "danger")
        return redirect(url_for("admin.clinicas"))

    creada = sb.table("clinicas").insert({
        "nombre": nombre,
        "slug": _slug_libre(_slug(nombre)),
        "ruc": ruc,
        "telefono": (request.form.get("telefono") or "").strip() or None,
        "direccion": (request.form.get("direccion") or "").strip() or None,
        "vence_el": _fecha_o_none(request.form.get("vence_el")),
        "modulos": _modulos_del_form() or list(MODULOS),
        "activa": True,
    }).execute().data

    flash(f"Clínica «{nombre}» creada. Ahora crea su usuario titular.", "success")
    return redirect(url_for("admin.clinica", clinica_id=creada[0]["id"]))


@bp.route("/clinicas/<int:clinica_id>")
@requiere_superadmin
def clinica(clinica_id):
    filas = sb.table("clinicas").select("*").eq("id", clinica_id).limit(1).execute().data
    if not filas:
        abort(404)
    usuarios = (
        sb.table("usuarios").select("*")
        .eq("clinica_id", clinica_id).order("nombre").execute().data or []
    )
    return render_template("admin/clinica.html", clinica=filas[0], usuarios=usuarios,
                           modulos=MODULOS, roles=ROLES, clave_defecto=CLAVE_POR_DEFECTO)


@bp.route("/clinicas/<int:clinica_id>/guardar", methods=["POST"])
@requiere_superadmin
def guardar_clinica(clinica_id):
    ruc, error_ruc = validar_ruc(request.form.get("ruc"))
    if error_ruc:
        flash(error_ruc, "danger")
        return redirect(url_for("admin.clinica", clinica_id=clinica_id))

    cambios = {
        "nombre": (request.form.get("nombre") or "").strip(),
        "ruc": ruc,
        "telefono": (request.form.get("telefono") or "").strip() or None,
        "telefono2": (request.form.get("telefono2") or "").strip() or None,
        "telefono3": (request.form.get("telefono3") or "").strip() or None,
        "direccion": (request.form.get("direccion") or "").strip() or None,
        "activa": request.form.get("activa") == "on",
        "vence_el": _fecha_o_none(request.form.get("vence_el")),
        "modulos": _modulos_del_form(),
    }

    filas = sb.table("clinicas").select("logo_path").eq("id", clinica_id).limit(1).execute().data
    anterior = filas[0].get("logo_path") if filas else None

    if request.form.get("quitar_logo") == "on":
        cambios["logo_url"] = None
        cambios["logo_path"] = None
        if anterior:
            borrar_imagen(anterior)

    archivo = request.files.get("logo")
    if archivo and archivo.filename:
        try:
            subido = subir_logo(archivo, clinica_id)
        except ErrorSubida as e:
            flash(str(e), "danger")
            return redirect(url_for("admin.clinica", clinica_id=clinica_id))
        cambios["logo_url"] = subido["url"]
        cambios["logo_path"] = subido["storage_path"]
        if anterior:
            borrar_imagen(anterior)      # el viejo ya no lo referencia nadie

    sb.table("clinicas").update(cambios).eq("id", clinica_id).execute()
    flash("Clínica actualizada.", "success")
    return redirect(url_for("admin.clinica", clinica_id=clinica_id))


@bp.route("/clinicas/<int:clinica_id>/renovar", methods=["POST"])
@requiere_superadmin
def renovar(clinica_id):
    """Suma un mes a la mensualidad, desde hoy o desde el vencimiento si aún no pasó."""
    filas = sb.table("clinicas").select("vence_el").eq("id", clinica_id).limit(1).execute().data
    if not filas:
        abort(404)
    actual = filas[0].get("vence_el")
    base = date.fromisoformat(actual) if actual else date.today()
    if base < date.today():
        base = date.today()
    nuevo = _sumar_un_mes(base)

    sb.table("clinicas").update(
        {"vence_el": nuevo.isoformat(), "activa": True}
    ).eq("id", clinica_id).execute()
    flash(f"Mensualidad renovada hasta el {nuevo.strftime('%d/%m/%Y')}.", "success")
    return redirect(url_for("admin.clinica", clinica_id=clinica_id))


# ---------------------------------------------------------------------
# Usuarios de una clínica
# ---------------------------------------------------------------------

@bp.route("/clinicas/<int:clinica_id>/usuarios/nuevo", methods=["POST"])
@requiere_superadmin
def nuevo_usuario(clinica_id):
    nombre = (request.form.get("nombre") or "").strip()
    acceso = (request.form.get("usuario") or "").strip()
    # El correo es opcional: no sirve para entrar, solo para recuperar la
    # clave y mandar avisos.
    email = (request.form.get("email") or "").strip().lower() or None

    if not nombre or not acceso:
        flash("Nombre y usuario son obligatorios.", "danger")
        return redirect(url_for("admin.clinica", clinica_id=clinica_id))

    ocupado = _ocupado(acceso, email)
    if ocupado:
        flash(ocupado, "danger")
        return redirect(url_for("admin.clinica", clinica_id=clinica_id))

    rol = request.form.get("rol") if request.form.get("rol") in ("dueno", "usuario") else "usuario"
    clave = (request.form.get("clave") or "").strip() or CLAVE_POR_DEFECTO

    sb.table("usuarios").insert({
        "clinica_id": clinica_id,
        "nombre": nombre,
        "usuario": acceso,
        "email": email,
        "password_hash": hashear(clave),
        "rol": rol,
        # El titular ve todo el plan; a un usuario normal se le reparte después.
        "modulos": list(MODULOS) if rol == "dueno" else _modulos_del_form(),
        "activo": True,
    }).execute()

    flash(f"Usuario «{acceso}» creado. Contraseña inicial: {clave}", "success")
    return redirect(url_for("admin.clinica", clinica_id=clinica_id))


@bp.route("/usuarios/<int:usuario_id>/guardar", methods=["POST"])
@requiere_superadmin
def guardar_usuario(usuario_id):
    filas = sb.table("usuarios").select("clinica_id, rol, usuario").eq("id", usuario_id).limit(1).execute().data
    if not filas:
        abort(404)
    previo = filas[0]
    rol = request.form.get("rol") if request.form.get("rol") in ("dueno", "usuario") else previo["rol"]
    acceso = (request.form.get("usuario") or "").strip() or previo["usuario"]
    email = (request.form.get("email") or "").strip().lower() or None

    ocupado = _ocupado(acceso, email, excluir_id=usuario_id)
    if ocupado:
        flash(ocupado, "danger")
        return redirect(url_for("admin.clinica", clinica_id=previo["clinica_id"]))

    sb.table("usuarios").update({
        "nombre": (request.form.get("nombre") or "").strip(),
        "usuario": acceso,
        "email": email,
        "rol": rol,
        "activo": request.form.get("activo") == "on",
        "modulos": list(MODULOS) if rol == "dueno" else _modulos_del_form(),
    }).eq("id", usuario_id).execute()

    flash("Usuario actualizado.", "success")
    return redirect(url_for("admin.clinica", clinica_id=previo["clinica_id"]))


@bp.route("/usuarios/<int:usuario_id>/clave", methods=["POST"])
@requiere_superadmin
def reiniciar_clave(usuario_id):
    filas = sb.table("usuarios").select("clinica_id, usuario").eq("id", usuario_id).limit(1).execute().data
    if not filas:
        abort(404)
    clave = (request.form.get("clave") or "").strip() or CLAVE_POR_DEFECTO

    sb.table("usuarios").update({"password_hash": hashear(clave)}).eq("id", usuario_id).execute()
    flash(f"Contraseña de «{filas[0]['usuario']}» cambiada a: {clave}", "success")
    return redirect(url_for("admin.clinica", clinica_id=filas[0]["clinica_id"]))


@bp.route("/usuarios/<int:usuario_id>/eliminar", methods=["POST"])
@requiere_superadmin
def eliminar_usuario(usuario_id):
    filas = sb.table("usuarios").select("clinica_id").eq("id", usuario_id).limit(1).execute().data
    if not filas:
        abort(404)
    if usuario_actual() and usuario_actual()["id"] == usuario_id:
        flash("No puedes eliminar tu propia cuenta.", "danger")
    else:
        sb.table("usuarios").delete().eq("id", usuario_id).execute()
        flash("Usuario eliminado.", "info")
    return redirect(url_for("admin.clinica", clinica_id=filas[0]["clinica_id"]))


# ---------------------------------------------------------------------
# Reportes que mandan las clínicas
# ---------------------------------------------------------------------

@bp.route("/reportes")
@requiere_superadmin
def reportes():
    filas = (
        sb.table("reportes_plataforma")
        .select("*, clinicas(id, nombre), usuarios(usuario)")
        .order("creado_en", desc=True).limit(200).execute().data or []
    )
    estado = request.args.get("estado")
    if estado in ESTADOS_REPORTE:
        filas = [r for r in filas if r["estado"] == estado]

    return render_template("admin/reportes.html", reportes=filas,
                           tipos=TIPOS_REPORTE, estados=ESTADOS_REPORTE,
                           filtro=estado or "")


@bp.route("/reportes/<int:reporte_id>", methods=["POST"])
@requiere_superadmin
def responder_reporte(reporte_id):
    nuevo = request.form.get("estado")
    if nuevo not in ESTADOS_REPORTE:
        abort(400)

    cambios = {
        "estado": nuevo,
        "respuesta": (request.form.get("respuesta") or "").strip() or None,
        "resuelto_en": datetime.now(timezone.utc).isoformat() if nuevo == "resuelto" else None,
    }
    sb.table("reportes_plataforma").update(cambios).eq("id", reporte_id).execute()
    flash("Reporte actualizado.", "success")
    return redirect(url_for("admin.reportes", estado=request.form.get("volver_a") or None))
