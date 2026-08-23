"""Panel principal: cifras del día, próximas citas, ventas y alertas."""

from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, render_template

from services.auth import puede, sel


bp = Blueprint("dashboard", __name__)


def _ventas(desde: date, hasta: date) -> list:
    """
    Cobros del período con el profesional que hizo el tratamiento colgando.
    Se atribuye la venta a quien atendió, no a quien registró el cobro: es
    lo que responde "qué doctor produce más".
    """
    return (
        sel("pagos", "monto, fecha, tratamientos(profesional_id, profesionales(nombre))")
        .gte("fecha", desde.isoformat())
        .lte("fecha", hasta.isoformat())
        .execute().data or []
    )


def _resumen_ventas(hoy: date) -> dict:
    inicio_mes = hoy.replace(day=1)
    pagos = _ventas(min(inicio_mes, hoy - timedelta(days=6)), hoy)

    total_hoy = total_mes = 0.0
    por_profesional: dict = {}
    por_dia = {(hoy - timedelta(days=n)).isoformat(): 0.0 for n in range(6, -1, -1)}

    for p in pagos:
        monto = float(p["monto"] or 0)
        fecha = p["fecha"]

        if fecha == hoy.isoformat():
            total_hoy += monto
        if fecha >= inicio_mes.isoformat():
            total_mes += monto
            tratamiento = p.get("tratamientos") or {}
            profesional = (tratamiento.get("profesionales") or {}).get("nombre")
            clave = profesional or "Sin profesional asignado"
            por_profesional[clave] = por_profesional.get(clave, 0.0) + monto
        if fecha in por_dia:
            por_dia[fecha] += monto

    ranking = sorted(por_profesional.items(), key=lambda x: x[1], reverse=True)[:5]
    tope_dia = max(por_dia.values()) or 1.0

    return {
        "hoy": round(total_hoy, 2),
        "mes": round(total_mes, 2),
        "ranking": [{"nombre": n, "monto": round(m, 2)} for n, m in ranking],
        "tope_ranking": ranking[0][1] if ranking else 1.0,
        "dias": [
            {"fecha": f, "monto": round(m, 2), "alto": round(m / tope_dia * 100)}
            for f, m in por_dia.items()
        ],
    }


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

    # --- Alertas del almacén: falta stock, está por vencer o está malogrado --
    # Son tres cosas distintas: un instrumental puede tener stock de sobra y
    # aun así estar inservible, y eso también hay que avisarlo.
    productos = (
        sel("productos_almacen", "id, nombre, stock_actual, stock_minimo, unidad_medida, "
                                 "tiene_vencimiento, fecha_vencimiento, estado, nota_estado")
        .eq("activo", True).execute().data or []
    )
    hoy_fecha = date.today()
    alertas_stock_bajo, alertas_vencimiento, alertas_mal_estado = [], [], []
    for p in productos:
        if p.get("estado") == "mal_estado":
            alertas_mal_estado.append(p)
        if p["stock_minimo"] is not None and float(p["stock_actual"]) <= float(p["stock_minimo"]):
            alertas_stock_bajo.append(p)
        if p["tiene_vencimiento"] and p["fecha_vencimiento"]:
            dias = (date.fromisoformat(p["fecha_vencimiento"]) - hoy_fecha).days
            if dias <= 30:
                p["dias_para_vencer"] = dias
                alertas_vencimiento.append(p)
    alertas_vencimiento.sort(key=lambda p: p["dias_para_vencer"])

    # Las cifras de dinero solo para quien tenga el módulo: una recepcionista
    # sin Presupuestos no debería ver la facturación de la clínica.
    ventas = _resumen_ventas(hoy) if puede("presupuestos") else None

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
        alertas_mal_estado=alertas_mal_estado,
        ventas=ventas,
        hoy=hoy,
    )
