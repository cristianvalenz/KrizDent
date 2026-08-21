"""Alta, baja y modificación de pacientes + vista de detalle."""

from flask import (Blueprint, Response, abort, flash, jsonify, redirect,
                   render_template, request, url_for)

from services.constantes import (ARCADAS, CARAS_PIEZA, ESTADOS_CARA,
                                  ESTADOS_ORTODONCIA, ESTADOS_PIEZA,
                                  TIPOS_MORDIDA, TIPOS_ORTODONCIA, TIPOS_PACIENTE)
from services.historial_pdf import generar_historial_pdf
from services.supabase_client import sb

bp = Blueprint("pacientes", __name__, url_prefix="/pacientes")


def _campos_del_formulario(form) -> dict:
    """Lee el formulario y normaliza: los campos vacíos se guardan como NULL, no como ''."""
    def limpio(clave):
        valor = (form.get(clave) or "").strip()
        return valor or None

    tipo_paciente = form.get("tipo_paciente")
    if tipo_paciente not in TIPOS_PACIENTE:
        tipo_paciente = "adulto"

    # "Sin alergias" siempre guarda NULL, sin importar qué haya quedado en el
    # textarea (deshabilitado en el form, pero no confiamos en el cliente).
    alergias = limpio("alergias") if form.get("tiene_alergias") == "si" else None

    return {
        "nombre": (form.get("nombre") or "").strip(),
        "documento": limpio("documento"),
        "fecha_nac": limpio("fecha_nac"),
        "telefono": limpio("telefono"),
        "email": limpio("email"),
        "direccion": limpio("direccion"),
        "alergias": alergias,
        "tipo_paciente": tipo_paciente,
    }


@bp.route("/")
def lista():
    """Listado con búsqueda por nombre, documento o teléfono."""
    q = (request.args.get("q") or "").strip()
    incluir_inactivos = request.args.get("inactivos") == "1"

    consulta = sb.table("pacientes").select("*")
    if not incluir_inactivos:
        consulta = consulta.eq("activo", True)
    if q:
        # or_ arma un OR de PostgREST: nombre ILIKE %q% OR documento ILIKE %q% ...
        consulta = consulta.or_(
            f"nombre.ilike.%{q}%,documento.ilike.%{q}%,telefono.ilike.%{q}%"
        )

    pacientes = consulta.order("nombre").execute().data or []
    return render_template(
        "pacientes/lista.html", pacientes=pacientes, q=q,
        incluir_inactivos=incluir_inactivos,
    )


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        datos = _campos_del_formulario(request.form)

        if not datos["nombre"]:
            flash("El nombre del paciente es obligatorio.", "danger")
            return render_template("pacientes/formulario.html", paciente=datos, modo="nuevo",
                                    tipos_paciente=TIPOS_PACIENTE)

        creado = sb.table("pacientes").insert(datos).execute().data[0]
        flash(f"Paciente {creado['nombre']} registrado.", "success")
        return redirect(url_for("pacientes.detalle", paciente_id=creado["id"]))

    return render_template("pacientes/formulario.html", paciente={}, modo="nuevo",
                            tipos_paciente=TIPOS_PACIENTE)


@bp.route("/<int:paciente_id>/editar", methods=["GET", "POST"])
def editar(paciente_id):
    paciente = _obtener_paciente(paciente_id)

    if request.method == "POST":
        datos = _campos_del_formulario(request.form)
        if not datos["nombre"]:
            flash("El nombre del paciente es obligatorio.", "danger")
            return render_template("pacientes/formulario.html", paciente=paciente, modo="editar",
                                    tipos_paciente=TIPOS_PACIENTE)

        sb.table("pacientes").update(datos).eq("id", paciente_id).execute()
        flash("Datos del paciente actualizados.", "success")
        return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))

    return render_template("pacientes/formulario.html", paciente=paciente, modo="editar",
                            tipos_paciente=TIPOS_PACIENTE)


@bp.route("/<int:paciente_id>/baja", methods=["POST"])
def baja(paciente_id):
    """
    Baja LÓGICA: marca activo=false y conserva historial y odontograma.
    Un historial clínico no se borra; se archiva.
    """
    paciente = _obtener_paciente(paciente_id)
    sb.table("pacientes").update({"activo": False}).eq("id", paciente_id).execute()
    flash(f"{paciente['nombre']} pasó a inactivos. Su historial sigue disponible.", "info")
    return redirect(url_for("pacientes.lista"))


@bp.route("/<int:paciente_id>/reactivar", methods=["POST"])
def reactivar(paciente_id):
    sb.table("pacientes").update({"activo": True}).eq("id", paciente_id).execute()
    flash("Paciente reactivado.", "success")
    return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))


@bp.route("/<int:paciente_id>/mordida", methods=["POST"])
def guardar_mordida(paciente_id):
    """Guarda el tipo de mordida aproximado. Se llama por AJAX desde el odontograma."""
    datos = request.get_json(silent=True) or {}
    mordida = datos.get("mordida") or None

    if mordida is not None and mordida not in TIPOS_MORDIDA:
        return jsonify({"ok": False, "error": f"Tipo de mordida «{mordida}» no reconocido."}), 400

    sb.table("pacientes").update({"mordida": mordida}).eq("id", paciente_id).execute()
    return jsonify({"ok": True, "mordida": mordida})


@bp.route("/<int:paciente_id>")
def detalle(paciente_id):
    """Ficha completa: datos, odontograma, historial clínico y citas."""
    paciente = _obtener_paciente(paciente_id)

    citas = (
        sb.table("citas").select("*").eq("paciente_id", paciente_id)
        .order("fecha_hora", desc=True).execute().data or []
    )

    entradas = (
        sb.table("historial").select("*, historial_imagenes(*)")
        .eq("paciente_id", paciente_id)
        .order("fecha", desc=True).order("id", desc=True)
        .execute().data or []
    )

    recetas = (
        sb.table("recetas").select("*").eq("paciente_id", paciente_id)
        .order("fecha", desc=True).order("id", desc=True)
        .execute().data or []
    )

    # El odontograma se envía como diccionario {pieza: {estado, perno}} para
    # que el JavaScript pinte el diagrama sin tener que recorrer una lista.
    filas = (
        sb.table("odontograma").select("pieza, estado, con_perno")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    odontograma = {
        str(f["pieza"]): {"estado": f["estado"], "perno": f["con_perno"]} for f in filas
    }

    # Caras marcadas (caries/obturado por mesial, distal, oclusal, etc.)
    filas_caras = (
        sb.table("odontograma_caras").select("pieza, cara, estado")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    odontograma_caras: dict = {}
    for f in filas_caras:
        odontograma_caras.setdefault(str(f["pieza"]), {})[f["cara"]] = f["estado"]

    ortodoncia = (
        sb.table("ortodoncia_aparatos").select("*")
        .eq("paciente_id", paciente_id).order("id").execute().data or []
    )

    return render_template(
        "pacientes/detalle.html",
        paciente=paciente,
        citas=citas,
        entradas=entradas,
        recetas=recetas,
        odontograma=odontograma,
        odontograma_caras=odontograma_caras,
        ortodoncia=ortodoncia,
        estados_pieza=ESTADOS_PIEZA,
        estados_cara=ESTADOS_CARA,
        colores_odontograma={**ESTADOS_PIEZA, **ESTADOS_CARA},
        caras_pieza=CARAS_PIEZA,
        tipos_mordida=TIPOS_MORDIDA,
        tipos_ortodoncia=TIPOS_ORTODONCIA,
        estados_ortodoncia=ESTADOS_ORTODONCIA,
        arcadas=ARCADAS,
    )


@bp.route("/<int:paciente_id>/historial/pdf")
def historial_pdf(paciente_id):
    """Descarga el historial clínico completo del paciente en una hoja A4:
    el odontograma actual arriba, y las entradas del historial abajo."""
    paciente = _obtener_paciente(paciente_id)
    entradas = (
        sb.table("historial").select("*, historial_imagenes(*)")
        .eq("paciente_id", paciente_id)
        .order("fecha", desc=True).order("id", desc=True)
        .execute().data or []
    )

    filas = (
        sb.table("odontograma").select("pieza, estado, con_perno")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    odontograma = {
        str(f["pieza"]): {"estado": f["estado"], "perno": f["con_perno"]} for f in filas
    }
    filas_caras = (
        sb.table("odontograma_caras").select("pieza, cara, estado")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    odontograma_caras: dict = {}
    for f in filas_caras:
        odontograma_caras.setdefault(str(f["pieza"]), {})[f["cara"]] = f["estado"]

    pdf = generar_historial_pdf(paciente, entradas, odontograma, odontograma_caras)
    nombre_archivo = f"historial_{paciente['nombre'].replace(' ', '_')}.pdf"

    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nombre_archivo}"'},
    )


def _obtener_paciente(paciente_id: int) -> dict:
    """Trae un paciente o corta con 404. Se reutiliza en varias rutas."""
    resp = sb.table("pacientes").select("*").eq("id", paciente_id).limit(1).execute()
    if not resp.data:
        abort(404)
    return resp.data[0]
