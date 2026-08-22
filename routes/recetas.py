"""Recetas médicas: alta, historial por paciente y descarga en PDF."""

from flask import Blueprint, Response, abort, jsonify, render_template, request, url_for

from services.receta_pdf import generar_receta_pdf
from services.auth import ins, sel


bp = Blueprint("recetas", __name__, url_prefix="/recetas")


@bp.route("/")
def lista():
    """Listado general de recetas de todos los pacientes, con búsqueda."""
    q = (request.args.get("q") or "").strip()

    consulta = (
        sel("recetas", "*, pacientes(id, nombre, documento, telefono)")
        .order("creado_en", desc=True)
    )
    recetas = consulta.execute().data or []

    if q:
        q_low = q.lower()
        recetas = [
            r for r in recetas
            if q_low in (r.get("pacientes") or {}).get("nombre", "").lower()
            or q_low in ((r.get("pacientes") or {}).get("documento") or "").lower()
            or q_low in (r.get("odontologo_nombre") or "").lower()
            or q_low in (r.get("contenido") or "").lower()
        ]

    return render_template("recetas/lista.html", recetas=recetas, q=q)


@bp.route("/nueva/<int:paciente_id>", methods=["GET", "POST"])
def nueva(paciente_id):
    """
    El formulario se envía por fetch (ver el <script> en recetas/formulario.html)
    para poder abrir el PDF en una pestaña nueva sin perder esta página: el POST
    devuelve JSON con el id de la receta creada, en vez de redirigir.
    """
    paciente = _obtener_paciente(paciente_id)

    if request.method == "POST":
        contenido = (request.form.get("contenido") or "").strip()
        if not contenido:
            return jsonify({"ok": False, "error": "La receta necesita al menos una indicación."}), 400

        creada = ins("recetas", {
            "paciente_id": paciente_id,
            "contenido": contenido,
            "odontologo_nombre": (request.form.get("odontologo_nombre") or "").strip() or None,
            "odontologo_cop": (request.form.get("odontologo_cop") or "").strip() or None,
        }).execute().data[0]

        return jsonify({
            "ok": True,
            "receta_id": creada["id"],
            "pdf_url": url_for("recetas.descargar", receta_id=creada["id"]),
        })

    return render_template("recetas/formulario.html", paciente=paciente)


@bp.route("/<int:receta_id>/pdf")
def descargar(receta_id):
    receta = _obtener_receta(receta_id)
    paciente = _obtener_paciente(receta["paciente_id"])

    pdf = generar_receta_pdf(receta, paciente)
    nombre_archivo = f"receta_{paciente['nombre'].replace(' ', '_')}_{receta['fecha']}.pdf"

    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nombre_archivo}"'},
    )


def _obtener_paciente(paciente_id: int) -> dict:
    resp = sel("pacientes", "*").eq("id", paciente_id).limit(1).execute()
    if not resp.data:
        abort(404)
    return resp.data[0]


def _obtener_receta(receta_id: int) -> dict:
    resp = sel("recetas", "*").eq("id", receta_id).limit(1).execute()
    if not resp.data:
        abort(404)
    return resp.data[0]
