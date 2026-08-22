"""Profesionales (odontólogos) que se pueden asignar a citas y tratamientos."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from services.supabase_client import sb

bp = Blueprint("profesionales", __name__, url_prefix="/profesionales")


@bp.route("/")
def lista():
    profesionales = (
        sb.table("profesionales").select("*").order("nombre").execute().data or []
    )
    return render_template("profesionales/lista.html", profesionales=profesionales)


@bp.route("/nuevo", methods=["POST"])
def nuevo():
    nombre = (request.form.get("nombre") or "").strip()
    if not nombre:
        flash("El profesional necesita un nombre.", "danger")
        return redirect(url_for("profesionales.lista"))

    sb.table("profesionales").insert({"nombre": nombre}).execute()
    flash(f"«{nombre}» agregado.", "success")
    return redirect(url_for("profesionales.lista"))


@bp.route("/<int:profesional_id>/estado", methods=["POST"])
def cambiar_estado(profesional_id):
    activo = request.form.get("activo") == "1"
    sb.table("profesionales").update({"activo": activo}).eq("id", profesional_id).execute()
    return redirect(url_for("profesionales.lista"))
