"""Reportes: ingresos por mes, tratamientos más frecuentes, pacientes nuevos."""

from collections import Counter, defaultdict
from datetime import date

from flask import Blueprint, render_template

from services.auth import sel


bp = Blueprint("reportes", __name__, url_prefix="/reportes")

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"]


@bp.route("/")
def index():
    hoy = date.today()
    # Últimos 6 meses, en orden cronológico (el actual al final).
    claves_mes = []
    y, m = hoy.year, hoy.month
    for _ in range(6):
        claves_mes.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    claves_mes.reverse()

    def etiqueta_mes(clave):
        y, m = clave.split("-")
        return f"{MESES[int(m) - 1]} {y[2:]}"

    # --- Ingresos por mes (suma de pagos) -----------------------------------
    pagos = sel("pagos", "monto, fecha").execute().data or []
    ingresos_por_mes = defaultdict(float)
    for p in pagos:
        clave = (p["fecha"] or "")[:7]
        ingresos_por_mes[clave] += float(p["monto"])

    ingresos = [round(ingresos_por_mes.get(c, 0), 2) for c in claves_mes]

    # --- Pacientes nuevos por mes --------------------------------------------
    pacientes = sel("pacientes", "creado_en").execute().data or []
    nuevos_por_mes = Counter((p["creado_en"] or "")[:7] for p in pacientes)
    nuevos = [nuevos_por_mes.get(c, 0) for c in claves_mes]

    # --- Tratamientos más frecuentes (por descripción, texto libre) ----------
    tratamientos = sel("tratamientos", "descripcion, costo").execute().data or []
    conteo_tratamientos = Counter(t["descripcion"].strip() for t in tratamientos if t.get("descripcion"))
    top_tratamientos = conteo_tratamientos.most_common(8)

    total_facturado = sum(float(t["costo"]) for t in tratamientos)
    total_cobrado = sum(float(p["monto"]) for p in pagos)

    return render_template(
        "reportes/index.html",
        etiquetas_mes=[etiqueta_mes(c) for c in claves_mes],
        ingresos=ingresos,
        nuevos=nuevos,
        top_tratamientos=top_tratamientos,
        total_facturado=total_facturado,
        total_cobrado=total_cobrado,
        total_pacientes=len(pacientes),
    )
