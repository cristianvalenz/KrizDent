"""Historial clínico: entradas por paciente con imágenes adjuntas."""

from flask import Blueprint, flash, redirect, request, url_for

from services.storage import ErrorSubida, borrar_imagen, subir_imagen
from services.auth import dele, ins, sel, upd


bp = Blueprint("historial", __name__, url_prefix="/historial")


@bp.route("/<int:paciente_id>/nueva", methods=["POST"])
def nueva(paciente_id):
    """
    Crea una entrada de historial y sube las imágenes que la acompañen.
    El formulario vive dentro de la ficha del paciente (modal "Nueva entrada").
    """
    diagnostico = (request.form.get("diagnostico") or "").strip()
    tratamiento = (request.form.get("tratamiento") or "").strip()

    if not diagnostico and not tratamiento:
        flash("Escribe al menos un diagnóstico o un tratamiento.", "danger")
        return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))

    entrada = ins("historial", {
        "paciente_id": paciente_id,
        "fecha": request.form.get("fecha") or None,
        "diagnostico": diagnostico or None,
        "tratamiento": tratamiento or None,
        "notas": (request.form.get("notas") or "").strip() or None,
    }).execute().data[0]

    # request.files.getlist permite varias imágenes en un solo input (multiple).
    archivos = [f for f in request.files.getlist("imagenes") if f and f.filename]
    subidas, fallos = 0, []

    for archivo in archivos:
        try:
            datos = subir_imagen(archivo, paciente_id)
            ins("historial_imagenes", {
                "historial_id": entrada["id"],
                "storage_path": datos["storage_path"],
                "url": datos["url"],
                "nombre_orig": datos["nombre_orig"],
            }).execute()
            subidas += 1
        except ErrorSubida as e:
            fallos.append(str(e))

    if subidas:
        flash(f"Entrada guardada con {subidas} imagen(es).", "success")
    else:
        flash("Entrada guardada en el historial.", "success")
    for f in fallos:
        flash(f, "warning")

    return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))


@bp.route("/<int:entrada_id>/editar", methods=["POST"])
def editar(entrada_id):
    paciente_id = int(request.form["paciente_id"])

    upd("historial", {
        "fecha": request.form.get("fecha") or None,
        "diagnostico": (request.form.get("diagnostico") or "").strip() or None,
        "tratamiento": (request.form.get("tratamiento") or "").strip() or None,
        "notas": (request.form.get("notas") or "").strip() or None,
    }).eq("id", entrada_id).execute()

    # Permite agregar imágenes a una entrada ya existente.
    for archivo in [f for f in request.files.getlist("imagenes") if f and f.filename]:
        try:
            datos = subir_imagen(archivo, paciente_id)
            ins("historial_imagenes", {
                "historial_id": entrada_id,
                "storage_path": datos["storage_path"],
                "url": datos["url"],
                "nombre_orig": datos["nombre_orig"],
            }).execute()
        except ErrorSubida as e:
            flash(str(e), "warning")

    flash("Entrada actualizada.", "success")
    return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))


@bp.route("/<int:entrada_id>/eliminar", methods=["POST"])
def eliminar(entrada_id):
    paciente_id = int(request.form["paciente_id"])

    # Borramos primero los archivos del bucket; el ON DELETE CASCADE
    # se encarga después de las filas de historial_imagenes.
    imagenes = (
        sel("historial_imagenes", "storage_path")
        .eq("historial_id", entrada_id).execute().data or []
    )
    for img in imagenes:
        borrar_imagen(img["storage_path"])

    dele("historial").eq("id", entrada_id).execute()
    flash("Entrada eliminada del historial.", "info")
    return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))


@bp.route("/imagen/<int:imagen_id>/eliminar", methods=["POST"])
def eliminar_imagen(imagen_id):
    paciente_id = int(request.form["paciente_id"])

    resp = sel("historial_imagenes", "storage_path").eq("id", imagen_id).execute()
    if resp.data:
        borrar_imagen(resp.data[0]["storage_path"])

    dele("historial_imagenes").eq("id", imagen_id).execute()
    flash("Imagen eliminada.", "info")
    return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))
