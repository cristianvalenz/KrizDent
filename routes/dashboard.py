"""Panel principal: cifras del día y próximas citas."""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template

from services.supabase_client import sb

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    hoy = datetime.now(timezone.utc).date()
    inicio_hoy = datetime.combine(hoy, datetime.min.time(), tzinfo=timezone.utc)
    fin_hoy = inicio_hoy + timedelta(days=1)
    fin_semana = inicio_hoy + timedelta(days=7)

    # count="exact" + limit(0) trae solo el número, no las filas: mucho más rápido.
    total_pacientes = (
        sb.table("pacientes").select("id", count="exact")
        .eq("activo", True).limit(0).execute().count or 0
    )

    citas_hoy = (
        sb.table("citas")
        .select("*, pacientes(id, nombre)")
        .gte("fecha_hora", inicio_hoy.isoformat())
        .lt("fecha_hora", fin_hoy.isoformat())
        .order("fecha_hora")
        .execute().data or []
    )

    proximas = (
        sb.table("citas")
        .select("*, pacientes(id, nombre)")
        .gte("fecha_hora", fin_hoy.isoformat())
        .lt("fecha_hora", fin_semana.isoformat())
        .eq("estado", "pendiente")
        .order("fecha_hora")
        .limit(8)
        .execute().data or []
    )

    pendientes_total = (
        sb.table("citas").select("id", count="exact")
        .eq("estado", "pendiente")
        .gte("fecha_hora", inicio_hoy.isoformat())
        .limit(0).execute().count or 0
    )

    ultimos_pacientes = (
        sb.table("pacientes").select("id, nombre, creado_en, telefono")
        .eq("activo", True).order("creado_en", desc=True).limit(5)
        .execute().data or []
    )

    # Distribución de piezas con hallazgos, para la barra del panel.
    piezas = (
        sb.table("odontograma").select("estado").neq("estado", "sano")
        .execute().data or []
    )
    resumen_piezas = {}
    for p in piezas:
        resumen_piezas[p["estado"]] = resumen_piezas.get(p["estado"], 0) + 1

    return render_template(
        "index.html",
        total_pacientes=total_pacientes,
        citas_hoy=citas_hoy,
        proximas=proximas,
        pendientes_total=pendientes_total,
        ultimos_pacientes=ultimos_pacientes,
        resumen_piezas=resumen_piezas,
        hoy=hoy,
    )
