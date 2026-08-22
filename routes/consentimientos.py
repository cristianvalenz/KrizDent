"""
Consentimiento informado con firma digital.

La firma se dibuja en un <canvas> en el navegador (static/js/firma.js) y se
manda al backend como PNG en base64. Se sube a Supabase Storage igual que
las radiografías del historial — no hay tabla nueva de archivos, solo la
URL guardada en "consentimientos".
"""

import base64
import binascii
import uuid

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services.auth import datos_clinica, dele, ins, sel
from services.constantes import CONSENTIMIENTO_TEXTO_BASE
from services.storage import ErrorSubida, subir_bytes


def _texto_base() -> str:
    """El consentimiento lo firma el paciente con la clínica que lo atiende."""
    return CONSENTIMIENTO_TEXTO_BASE.format(clinica=datos_clinica()["nombre"])


bp = Blueprint("consentimientos", __name__, url_prefix="/consentimientos")


@bp.route("/pacientes/<int:paciente_id>/nuevo", methods=["GET", "POST"])
def nuevo(paciente_id):
    paciente = _obtener_paciente(paciente_id)

    if request.method == "POST":
        titulo = (request.form.get("titulo") or "Consentimiento informado").strip()
        texto = (request.form.get("texto") or "").strip()
        firma_datauri = request.form.get("firma") or ""

        if not texto:
            flash("Falta el texto del consentimiento.", "danger")
            return render_template("consentimientos/formulario.html", paciente=paciente,
                                    texto_base=_texto_base())

        if "," not in firma_datauri:
            flash("Falta la firma. Dibújala en el recuadro antes de guardar.", "danger")
            return render_template("consentimientos/formulario.html", paciente=paciente,
                                    texto_base=_texto_base())

        try:
            contenido = base64.b64decode(firma_datauri.split(",", 1)[1])
        except (binascii.Error, IndexError):
            flash("La firma no se pudo leer. Intenta firmar de nuevo.", "danger")
            return render_template("consentimientos/formulario.html", paciente=paciente,
                                    texto_base=_texto_base())

        try:
            url = subir_bytes(
                contenido,
                ruta=f"pacientes/{paciente_id}/firmas/{uuid.uuid4().hex}.png",
                content_type="image/png",
            )
        except ErrorSubida as e:
            flash(str(e), "danger")
            return render_template("consentimientos/formulario.html", paciente=paciente,
                                    texto_base=_texto_base())

        ins("consentimientos", {
            "paciente_id": paciente_id,
            "titulo": titulo,
            "texto": texto,
            "firma_url": url,
        }).execute()

        flash("Consentimiento firmado y guardado.", "success")
        return redirect(url_for("pacientes.detalle", paciente_id=paciente_id))

    return render_template("consentimientos/formulario.html", paciente=paciente,
                            texto_base=_texto_base())


@bp.route("/<int:consentimiento_id>/eliminar", methods=["POST"])
def eliminar(consentimiento_id):
    fila = sel("consentimientos", "paciente_id").eq("id", consentimiento_id).limit(1).execute().data
    if not fila:
        abort(404)
    dele("consentimientos").eq("id", consentimiento_id).execute()
    flash("Consentimiento eliminado.", "info")
    return redirect(url_for("pacientes.detalle", paciente_id=fila[0]["paciente_id"]))


def _obtener_paciente(paciente_id: int) -> dict:
    resp = sel("pacientes", "*").eq("id", paciente_id).limit(1).execute()
    if not resp.data:
        abort(404)
    return resp.data[0]
