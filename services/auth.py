"""
Sesión, permisos y aislamiento por clínica.

El sistema es multi-inquilino: cada clínica que alquila KrizDent ve solo sus
propios datos. Ese aislamiento NO se deja al criterio de cada consulta —
se centraliza en los ayudantes sel/ins/upd/dele de este módulo, que inyectan
solos el clinica_id de la sesión. Una consulta que use sb.table() directamente
se salta el aislamiento y podría mostrar pacientes de otra clínica; por eso
los módulos operativos deben usar siempre estos ayudantes.

El superadministrador (dueño de la plataforma) no pertenece a ninguna clínica:
su clinica_id es nulo, y el guardia de abajo solo lo deja entrar al panel de
administración. Así, quien alquila el sistema nunca ve historias clínicas.
"""

from datetime import date, datetime, timezone
from functools import wraps

from flask import flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from services.constantes import MODULO_DE_BLUEPRINT, MODULOS
from services.supabase_client import sb

# Endpoints que se pueden ver sin haber iniciado sesión.
LIBRES = {"auth.entrar", "static"}
# Blueprints que un usuario de clínica puede usar siempre, sin importar su plan.
SIEMPRE = {"auth"}


# ---------------------------------------------------------------------
# Contraseñas
# ---------------------------------------------------------------------

def hashear(clave: str) -> str:
    return generate_password_hash(clave)


def clave_correcta(usuario: dict, clave: str) -> bool:
    return check_password_hash(usuario.get("password_hash") or "", clave)


# ---------------------------------------------------------------------
# Sesión
# ---------------------------------------------------------------------

def _olvidar_cache() -> None:
    """
    usuario_actual() y clinica_actual() cachean su resultado en g para no
    consultar dos veces por petición. Al entrar o salir ese caché queda
    desactualizado dentro de la MISMA petición, así que hay que soltarlo:
    si no, justo después del login se seguiría viendo "sin sesión".
    """
    g.pop("usuario", None)
    g.pop("clinica", None)


def iniciar_sesion(usuario: dict) -> None:
    session.clear()
    session["usuario_id"] = usuario["id"]
    session.permanent = True
    _olvidar_cache()
    sb.table("usuarios").update(
        {"ultimo_acceso": datetime.now(timezone.utc).isoformat()}
    ).eq("id", usuario["id"]).execute()


def cerrar_sesion() -> None:
    session.clear()
    _olvidar_cache()


def usuario_actual():
    """El usuario de la sesión, leído una sola vez por petición."""
    if "usuario" in g:
        return g.usuario
    g.usuario = None
    uid = session.get("usuario_id")
    if uid:
        filas = sb.table("usuarios").select("*").eq("id", uid).limit(1).execute().data
        if filas and filas[0]["activo"]:
            g.usuario = filas[0]
    return g.usuario


def clinica_actual():
    """La clínica del usuario en sesión (None si es superadministrador)."""
    if "clinica" in g:
        return g.clinica
    g.clinica = None
    usuario = usuario_actual()
    if usuario and usuario.get("clinica_id"):
        filas = sb.table("clinicas").select("*").eq("id", usuario["clinica_id"]).limit(1).execute().data
        g.clinica = filas[0] if filas else None
    return g.clinica


def clinica_id() -> int:
    """Id de la clínica en sesión. Falla fuerte si no hay: nunca consultar sin ella."""
    clinica = clinica_actual()
    if not clinica:
        raise RuntimeError(
            "Consulta a datos de clínica sin clínica en sesión. "
            "El superadministrador no debe entrar a los módulos operativos."
        )
    return clinica["id"]


def datos_clinica() -> dict:
    """
    Membrete para los PDF (recetas, historia clínica). Sale de la clínica en
    sesión, no de la constante CLINICA: si no, una clínica que alquila el
    sistema imprimiría sus recetas con el nombre y la dirección de KrizDent.
    """
    from services.constantes import CLINICA          # import local: evita el ciclo

    actual = clinica_actual()
    if not actual:
        return dict(CLINICA)
    return {
        "nombre": actual["nombre"],
        "celular": actual.get("telefono") or "",
        "direccion": actual.get("direccion") or "",
        "eslogan": CLINICA["eslogan"],
    }


def es_superadmin() -> bool:
    usuario = usuario_actual()
    return bool(usuario and usuario["rol"] == "superadmin")


# ---------------------------------------------------------------------
# Permisos
# ---------------------------------------------------------------------

def modulos_visibles() -> list:
    """
    Lo que el usuario ve = lo que su clínica contrató ∩ lo que su titular le
    asignó. El titular de la clínica ve todo el plan sin necesidad de reparto.
    """
    clinica = clinica_actual()
    usuario = usuario_actual()
    if not clinica or not usuario:
        return []
    del_plan = [m for m in (clinica.get("modulos") or []) if m in MODULOS]
    if usuario["rol"] == "dueno":
        return del_plan
    propios = set(usuario.get("modulos") or [])
    return [m for m in del_plan if m in propios]


def puede(modulo: str) -> bool:
    return modulo in modulos_visibles()


def suscripcion_vigente(clinica: dict) -> bool:
    if not clinica or not clinica.get("activa"):
        return False
    vence = clinica.get("vence_el")
    if not vence:
        return True                      # sin fecha = sin vencimiento
    if isinstance(vence, str):
        vence = date.fromisoformat(vence)
    return vence >= date.today()


# ---------------------------------------------------------------------
# Guardia global
# ---------------------------------------------------------------------

def registrar_guardia(app):
    """
    Un único punto de control antes de cada petición. Se hace así, y no con un
    decorador por vista, porque un decorador se puede olvidar al agregar una
    ruta nueva — y aquí el olvido significaría filtrar historias clínicas.
    """

    @app.before_request
    def _guardia():
        endpoint = request.endpoint
        if endpoint is None or endpoint in LIBRES:
            return None

        usuario = usuario_actual()
        if not usuario:
            if request.method == "POST" or request.headers.get("Accept", "").startswith("application/json"):
                return {"ok": False, "error": "Sesión expirada"}, 401
            return redirect(url_for("auth.entrar", siguiente=request.full_path))

        blueprint = request.blueprint or ""
        if blueprint in SIEMPRE:
            return None

        # El superadministrador solo administra la plataforma.
        if usuario["rol"] == "superadmin":
            if blueprint == "admin":
                return None
            return redirect(url_for("admin.clinicas"))

        # A partir de aquí es un usuario de clínica: el panel de administración
        # de la plataforma le queda fuera del alcance.
        if blueprint == "admin":
            return render_template("error.html", codigo=403,
                                   titulo="Sin acceso",
                                   detalle="Esta zona es solo del administrador de la plataforma."), 403

        clinica = clinica_actual()
        if not suscripcion_vigente(clinica):
            return render_template("auth/suscripcion.html", clinica=clinica), 402

        modulo = MODULO_DE_BLUEPRINT.get(blueprint)
        if modulo and not puede(modulo):
            return render_template("error.html", codigo=403,
                                   titulo="Módulo no disponible",
                                   detalle=f"Tu cuenta no tiene acceso a «{MODULOS.get(modulo, modulo)}». "
                                           "Pídeselo al titular de la clínica."), 403
        return None

    @app.context_processor
    def _contexto():
        """Lo que la plantilla base necesita para pintar el menú y el usuario."""
        return {
            "usuario_sesion": usuario_actual(),
            "clinica_sesion": clinica_actual(),
            "modulos_visibles": modulos_visibles(),
            "es_superadmin": es_superadmin(),
        }


def requiere_superadmin(vista):
    """Refuerzo por vista para el blueprint de administración."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not es_superadmin():
            flash("Solo el administrador de la plataforma puede hacer eso.", "danger")
            return redirect(url_for("auth.entrar"))
        return vista(*args, **kwargs)
    return envoltura


# ---------------------------------------------------------------------
# Consultas con aislamiento automático
# ---------------------------------------------------------------------

def sel(tabla: str, columnas: str = "*", **kw):
    """SELECT ya filtrado por la clínica de la sesión."""
    return sb.table(tabla).select(columnas, **kw).eq("clinica_id", clinica_id())


def ins(tabla: str, datos):
    """INSERT con el clinica_id de la sesión puesto automáticamente."""
    cid = clinica_id()
    if isinstance(datos, list):
        datos = [{**fila, "clinica_id": cid} for fila in datos]
    else:
        datos = {**datos, "clinica_id": cid}
    return sb.table(tabla).insert(datos)


def ups(tabla: str, datos, **kw):
    """
    UPSERT con el clinica_id puesto. No lleva filtro .eq() porque el conflicto
    lo resuelve la clave única de la tabla; como esas claves cuelgan siempre de
    paciente_id (que ya es de una sola clínica), el aislamiento se mantiene.
    """
    cid = clinica_id()
    if isinstance(datos, list):
        datos = [{**fila, "clinica_id": cid} for fila in datos]
    else:
        datos = {**datos, "clinica_id": cid}
    return sb.table(tabla).upsert(datos, **kw)


def upd(tabla: str, datos: dict):
    """UPDATE que solo puede tocar filas de la clínica de la sesión."""
    return sb.table(tabla).update(datos).eq("clinica_id", clinica_id())


def dele(tabla: str):
    """DELETE que solo puede borrar filas de la clínica de la sesión."""
    return sb.table(tabla).delete().eq("clinica_id", clinica_id())
