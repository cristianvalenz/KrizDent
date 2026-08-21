"""Filtros Jinja para formatear fechas y datos en las plantillas."""

from datetime import date, datetime

MESES = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "set", "oct", "nov", "dic",
]


def _a_datetime(valor):
    """Convierte lo que devuelve Supabase (texto ISO) a datetime. None si no se puede."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day)
    try:
        # Supabase devuelve '2026-03-14T09:30:00+00:00'; fromisoformat lo entiende.
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


def fecha(valor):
    """2026-03-14 → 14 mar 2026"""
    dt = _a_datetime(valor)
    return f"{dt.day:02d} {MESES[dt.month - 1]} {dt.year}" if dt else "—"


def fecha_corta(valor):
    """2026-03-14 → 14/03/26"""
    dt = _a_datetime(valor)
    return dt.strftime("%d/%m/%y") if dt else "—"


def hora(valor):
    """2026-03-14T09:30 → 09:30"""
    dt = _a_datetime(valor)
    return dt.strftime("%H:%M") if dt else "—"


def fecha_hora(valor):
    """2026-03-14T09:30 → 14 mar 2026 · 09:30"""
    dt = _a_datetime(valor)
    return f"{fecha(dt)} · {dt.strftime('%H:%M')}" if dt else "—"


def input_datetime(valor):
    """Formato que necesita <input type="datetime-local">."""
    dt = _a_datetime(valor)
    return dt.strftime("%Y-%m-%dT%H:%M") if dt else ""


def input_fecha(valor):
    """Formato que necesita <input type="date">."""
    dt = _a_datetime(valor)
    return dt.strftime("%Y-%m-%d") if dt else ""


def edad(valor):
    """Calcula la edad en años a partir de la fecha de nacimiento."""
    dt = _a_datetime(valor)
    if not dt:
        return "—"
    hoy = date.today()
    años = hoy.year - dt.year - ((hoy.month, hoy.day) < (dt.month, dt.day))
    return f"{años} años"


def iniciales(nombre):
    """'María Fernanda Quispe' → 'MQ'  (para el avatar circular)."""
    partes = [p for p in (nombre or "").split() if p]
    if not partes:
        return "??"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def registrar_filtros(app):
    for f in (fecha, fecha_corta, hora, fecha_hora, input_datetime,
              input_fecha, edad, iniciales):
        app.jinja_env.filters[f.__name__] = f

    # Disponible en cualquier plantilla como {{ hoy }} y {{ ahora }}
    @app.context_processor
    def variables_globales():
        return {"hoy": date.today(), "ahora": datetime.now()}
