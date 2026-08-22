"""
Entrar, salir y gestionar la propia cuenta.

Este blueprint es el único accesible sin sesión, y por eso el guardia de
services/auth.py lo deja pasar entero: si lo bloqueara, nadie podría llegar
nunca a la pantalla de inicio de sesión.
"""

from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)

from services.auth import (clave_correcta, cerrar_sesion, hashear,
                           iniciar_sesion, modulos_visibles, usuario_actual)
from services.constantes import MODULOS
from services.supabase_client import sb


bp = Blueprint("auth", __name__)

# Dónde cae cada módulo al entrar, si el usuario no tiene "panel".
INICIO_DE_MODULO = {
    "panel":         "dashboard.index",
    "pacientes":     "pacientes.lista",
    "agenda":        "citas.lista",
    "presupuestos":  "finanzas.lista",
    "recetas":       "recetas.lista",
    "almacen":       "almacen.lista",
    "reportes":      "reportes.index",
    "profesionales": "profesionales.lista",
}


def _destino_tras_entrar(usuario) -> str:
    if usuario["rol"] == "superadmin":
        return url_for("admin.clinicas")
    for modulo in modulos_visibles():
        destino = INICIO_DE_MODULO.get(modulo)
        if destino:
            return url_for(destino)
    # Sin ningún módulo asignado: al menos que vea su cuenta y el aviso.
    return url_for("auth.perfil")


def _siguiente_seguro(valor: str) -> str:
    """Solo aceptamos rutas internas: un destino externo sería redirección abierta."""
    if valor and valor.startswith("/") and not valor.startswith("//"):
        return valor
    return ""


@bp.route("/entrar", methods=["GET", "POST"])
def entrar():
    if usuario_actual():
        return redirect(_destino_tras_entrar(usuario_actual()))

    siguiente = _siguiente_seguro(request.args.get("siguiente", ""))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        clave = request.form.get("clave") or ""

        filas = sb.table("usuarios").select("*").ilike("email", email).limit(1).execute().data
        usuario = filas[0] if filas else None

        # Mismo mensaje para usuario inexistente y clave mala: decir cuál de
        # los dos falló le confirmaría a un atacante qué correos existen.
        if not usuario or not usuario["activo"] or not clave_correcta(usuario, clave):
            flash("Correo o contraseña incorrectos.", "danger")
            return render_template("auth/entrar.html", email=email, siguiente=siguiente), 401

        iniciar_sesion(usuario)
        destino = _siguiente_seguro(request.form.get("siguiente", ""))
        return redirect(destino or _destino_tras_entrar(usuario))

    return render_template("auth/entrar.html", email="", siguiente=siguiente)


@bp.route("/salir", methods=["POST", "GET"])
def salir():
    cerrar_sesion()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.entrar"))


@bp.route("/perfil", methods=["GET", "POST"])
def perfil():
    """Cada quien puede cambiar su nombre y su propia contraseña."""
    usuario = usuario_actual()
    if not usuario:
        return redirect(url_for("auth.entrar"))

    if request.method == "POST":
        accion = request.form.get("accion")

        if accion == "datos":
            nombre = (request.form.get("nombre") or "").strip()
            if not nombre:
                flash("El nombre no puede quedar vacío.", "danger")
            else:
                sb.table("usuarios").update({"nombre": nombre}).eq("id", usuario["id"]).execute()
                flash("Datos actualizados.", "success")

        elif accion == "clave":
            actual = request.form.get("clave_actual") or ""
            nueva = request.form.get("clave_nueva") or ""
            repetir = request.form.get("clave_repetir") or ""

            if not clave_correcta(usuario, actual):
                flash("La contraseña actual no es correcta.", "danger")
            elif len(nueva) < 5:
                flash("La contraseña nueva debe tener al menos 5 caracteres.", "danger")
            elif nueva != repetir:
                flash("La contraseña nueva y su repetición no coinciden.", "danger")
            else:
                sb.table("usuarios").update(
                    {"password_hash": hashear(nueva)}
                ).eq("id", usuario["id"]).execute()
                flash("Contraseña actualizada.", "success")

        return redirect(url_for("auth.perfil"))

    return render_template("auth/perfil.html", usuario=usuario, modulos=MODULOS)
