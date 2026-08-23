"""Alta, baja y modificación de pacientes + vista de detalle."""

from flask import (Blueprint, Response, abort, flash, jsonify, redirect,
                   render_template, request, url_for)

from services.constantes import (ARCADAS, CARAS_PIEZA, ESTADOS_CARA,
                                  ESTADOS_LABORATORIO, ESTADOS_ORTODONCIA,
                                  ESTADOS_PIEZA, ESTADOS_TRATAMIENTO,
                                  METODOS_PAGO, TIPOS_MORDIDA, TIPOS_ORTODONCIA,
                                  TIPOS_PACIENTE)
from services.historial_pdf import generar_historial_pdf
from services.auth import ins, sel, upd


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

    consulta = sel("pacientes", "*")
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

        creado = ins("pacientes", datos).execute().data[0]
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

        upd("pacientes", datos).eq("id", paciente_id).execute()
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
    upd("pacientes", {"activo": False}).eq("id", paciente_id).execute()
    flash(f"{paciente['nombre']} pasó a inactivos. Su historial sigue disponible.", "info")
    return redirect(url_for("pacientes.lista"))


@bp.route("/<int:paciente_id>/reactivar", methods=["POST"])
def reactivar(paciente_id):
    upd("pacientes", {"activo": True}).eq("id", paciente_id).execute()
    flash("Paciente reactivado.", "success")
    return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))


@bp.route("/<int:paciente_id>/mordida", methods=["POST"])
def guardar_mordida(paciente_id):
    """Guarda el tipo de mordida aproximado. Se llama por AJAX desde el odontograma."""
    datos = request.get_json(silent=True) or {}
    mordida = datos.get("mordida") or None

    if mordida is not None and mordida not in TIPOS_MORDIDA:
        return jsonify({"ok": False, "error": f"Tipo de mordida «{mordida}» no reconocido."}), 400

    upd("pacientes", {"mordida": mordida}).eq("id", paciente_id).execute()
    return jsonify({"ok": True, "mordida": mordida})


@bp.route("/<int:paciente_id>")
def detalle(paciente_id):
    """Ficha completa: datos, odontograma, historial clínico y citas."""
    paciente = _obtener_paciente(paciente_id)

    citas = (
        sel("citas", "*").eq("paciente_id", paciente_id)
        .order("fecha_hora", desc=True).execute().data or []
    )

    entradas = (
        sel("historial", "*, historial_imagenes(*)")
        .eq("paciente_id", paciente_id)
        .order("fecha", desc=True).order("id", desc=True)
        .execute().data or []
    )

    recetas = (
        sel("recetas", "*").eq("paciente_id", paciente_id)
        .order("fecha", desc=True).order("id", desc=True)
        .execute().data or []
    )

    # El odontograma se envía como diccionario {pieza: {estado, perno}} para
    # que el JavaScript pinte el diagrama sin tener que recorrer una lista.
    filas = (
        sel("odontograma", "pieza, estado, con_perno")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    odontograma = {
        str(f["pieza"]): {"estado": f["estado"], "perno": f["con_perno"]} for f in filas
    }

    # Caras marcadas (caries/obturado por mesial, distal, oclusal, etc.)
    filas_caras = (
        sel("odontograma_caras", "pieza, cara, estado")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    odontograma_caras: dict = {}
    for f in filas_caras:
        odontograma_caras.setdefault(str(f["pieza"]), {})[f["cara"]] = f["estado"]

    ortodoncia = (
        sel("ortodoncia_aparatos", "*")
        .eq("paciente_id", paciente_id).order("id").execute().data or []
    )

    # --- Presupuesto y pagos --------------------------------------------
    tratamientos = (
        sel("tratamientos", "*").eq("paciente_id", paciente_id)
        .order("fecha", desc=True).execute().data or []
    )
    pagos = (
        sel("pagos", "*").eq("paciente_id", paciente_id)
        .order("fecha", desc=True).execute().data or []
    )
    total_presupuestado = sum(float(t["costo"]) for t in tratamientos if t["estado"] != "cancelado")
    total_pagado = sum(float(p["monto"]) for p in pagos)
    saldo_pendiente = round(total_presupuestado - total_pagado, 2)

    consentimientos = (
        sel("consentimientos", "*").eq("paciente_id", paciente_id)
        .order("firmado_en", desc=True).execute().data or []
    )
    laboratorio = (
        sel("trabajos_laboratorio", "*").eq("paciente_id", paciente_id)
        .order("fecha_envio", desc=True).execute().data or []
    )

    profesionales = (
        sel("profesionales", "id, nombre").eq("activo", True)
        .order("nombre").execute().data or []
    )

    # --- Versiones del odontograma (Inicial / Alta — "Evolución" es lo vivo) --
    versiones = (
        sel("odontograma_versiones", "tipo, fecha")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    version_inicial = next((v for v in versiones if v["tipo"] == "inicial"), None)
    version_alta = next((v for v in versiones if v["tipo"] == "alta"), None)

    periodontogramas = (
        sel("periodontogramas", "*").eq("paciente_id", paciente_id)
        .order("fecha", desc=True).execute().data or []
    )

    # --- Plan de tratamiento: piezas con hallazgo, para poder "vincular" cada
    # una a una línea de presupuesto desde el odontograma. Un hallazgo puede
    # estar a nivel de pieza completa (ausente, corona…) o solo en una cara
    # (caries, obturado…) — hay que mirar las dos tablas.
    plan_tratamiento = [
        {"pieza": p, "estado": info["estado"]}
        for p, info in odontograma.items() if info.get("estado") != "sano"
    ]
    piezas_con_pieza_completa = {h["pieza"] for h in plan_tratamiento}
    for p, caras in odontograma_caras.items():
        if p in piezas_con_pieza_completa:
            continue   # ya está listada por su estado de pieza completa
        estado_cara = next((e for e in caras.values() if e != "sano"), None)
        if estado_cara:
            plan_tratamiento.append({"pieza": p, "estado": estado_cara})
    plan_tratamiento.sort(key=lambda x: x["pieza"])

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
        tratamientos=tratamientos,
        pagos=pagos,
        total_presupuestado=total_presupuestado,
        total_pagado=total_pagado,
        saldo_pendiente=saldo_pendiente,
        estados_tratamiento=ESTADOS_TRATAMIENTO,
        metodos_pago=METODOS_PAGO,
        consentimientos=consentimientos,
        laboratorio=laboratorio,
        estados_laboratorio=ESTADOS_LABORATORIO,
        profesionales=profesionales,
        version_inicial=version_inicial,
        version_alta=version_alta,
        periodontogramas=periodontogramas,
        plan_tratamiento=plan_tratamiento,
    )


@bp.route("/<int:paciente_id>/historial/pdf")
def historial_pdf(paciente_id):
    """Descarga el historial clínico completo del paciente en una hoja A4:
    el odontograma y el periodontograma arriba, y las entradas abajo."""
    paciente = _obtener_paciente(paciente_id)
    entradas = (
        sel("historial", "*, historial_imagenes(*)")
        .eq("paciente_id", paciente_id)
        .order("fecha", desc=True).order("id", desc=True)
        .execute().data or []
    )

    filas = (
        sel("odontograma", "pieza, estado, con_perno")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    odontograma = {
        str(f["pieza"]): {"estado": f["estado"], "perno": f["con_perno"]} for f in filas
    }
    filas_caras = (
        sel("odontograma_caras", "pieza, cara, estado")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    odontograma_caras: dict = {}
    for f in filas_caras:
        odontograma_caras.setdefault(str(f["pieza"]), {})[f["cara"]] = f["estado"]

    # Solo el más reciente: el PDF retrata el estado actual del paciente, no
    # su histórico periodontal completo.
    periodontogramas = (
        sel("periodontogramas", "*")
        .eq("paciente_id", paciente_id)
        .order("fecha", desc=True).order("id", desc=True)
        .limit(1).execute().data or []
    )

    pdf = generar_historial_pdf(paciente, entradas, odontograma, odontograma_caras,
                                periodontogramas[0] if periodontogramas else None)
    nombre_archivo = f"historial_{paciente['nombre'].replace(' ', '_')}.pdf"

    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nombre_archivo}"'},
    )


def _obtener_paciente(paciente_id: int) -> dict:
    """Trae un paciente o corta con 404. Se reutiliza en varias rutas."""
    resp = sel("pacientes", "*").eq("id", paciente_id).limit(1).execute()
    if not resp.data:
        abort(404)
    return resp.data[0]
