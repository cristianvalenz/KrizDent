"""Panel principal: cifras del día y próximas citas."""

from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, render_template

from services.auth import sel


bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    hoy = datetime.now(timezone.utc).date()
    inicio_hoy = datetime.combine(hoy, datetime.min.time(), tzinfo=timezone.utc)
    fin_hoy = inicio_hoy + timedelta(days=1)
    fin_semana = inicio_hoy + timedelta(days=7)

    # count="exact" + limit(0) trae solo el número, no las filas: mucho más rápido.
    total_pacientes = (
        sel("pacientes", "id", count="exact")
        .eq("activo", True).limit(0).execute().count or 0
    )

    citas_hoy = (
        sel("citas", "*, pacientes(id, nombre)")
        .gte("fecha_hora", inicio_hoy.isoformat())
        .lt("fecha_hora", fin_hoy.isoformat())
        .order("fecha_hora")
        .execute().data or []
    )

    proximas = (
        sel("citas", "*, pacientes(id, nombre)")
        .gte("fecha_hora", fin_hoy.isoformat())
        .lt("fecha_hora", fin_semana.isoformat())
        .eq("estado", "pendiente")
        .order("fecha_hora")
        .limit(8)
        .execute().data or []
    )

    pendientes_total = (
        sel("citas", "id", count="exact")
        .eq("estado", "pendiente")
        .gte("fecha_hora", inicio_hoy.isoformat())
        .limit(0).execute().count or 0
    )

    ultimos_pacientes = (
        sel("pacientes", "id, nombre, creado_en, telefono")
        .eq("activo", True).order("creado_en", desc=True).limit(5)
        .execute().data or []
    )

    # Distribución de piezas con hallazgos, para la barra del panel.
    piezas = (
        sel("odontograma", "estado").neq("estado", "sano")
        .execute().data or []
    )
    resumen_piezas = {}
    for p in piezas:
        resumen_piezas[p["estado"]] = resumen_piezas.get(p["estado"], 0) + 1

    # --- Alertas del almacén: stock bajo o por vencer en ≤30 días -----------
    productos = (
        sel("productos_almacen", "id, nombre, stock_actual, stock_minimo, "
                                              "unidad_medida, tiene_vencimiento, fecha_vencimiento")
        .eq("activo", True).execute().data or []
    )
    hoy_fecha = date.today()
    alertas_stock_bajo, alertas_vencimiento = [], []
    for p in productos:
        if p["stock_minimo"] is not None and float(p["stock_actual"]) <= float(p["stock_minimo"]):
            alertas_stock_bajo.append(p)
        if p["tiene_vencimiento"] and p["fecha_vencimiento"]:
            dias = (date.fromisoformat(p["fecha_vencimiento"]) - hoy_fecha).days
            if dias <= 30:
                p["dias_para_vencer"] = dias
                alertas_vencimiento.append(p)
    alertas_vencimiento.sort(key=lambda p: p["dias_para_vencer"])

    return render_template(
        "index.html",
        total_pacientes=total_pacientes,
        citas_hoy=citas_hoy,
        proximas=proximas,
        pendientes_total=pendientes_total,
        ultimos_pacientes=ultimos_pacientes,
        resumen_piezas=resumen_piezas,
        alertas_stock_bajo=alertas_stock_bajo,
        alertas_vencimiento=alertas_vencimiento,
        hoy=hoy,
    )
