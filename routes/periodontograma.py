"""
Periodontograma: carta periodontal completa al estilo clínico.

Registra 6 sitios por pieza (3 vestibulares + 3 palatinos/linguales) con
margen gingival, profundidad de sondaje, placa, sangrado, supuración y furca,
más datos de la pieza entera (movilidad, pronóstico, ausencia, implante).

Los dientes se dibujan dentro de la misma cuadrícula que los datos: cada
pieza es una columna, así que la corona/raíz siempre queda alineada con sus
propias mediciones. Las curvas de margen gingival (azul) y fondo de bolsa
(rojo) se calculan aquí en Python y la plantilla solo las pinta.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from services.supabase_client import sb

bp = Blueprint("periodontograma", __name__, url_prefix="/periodontograma")

FILA_SUPERIOR_ADULTO = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]
FILA_INFERIOR_ADULTO = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
FILA_SUPERIOR_NINO = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65]
FILA_INFERIOR_NINO = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75]

CARAS = ["vestibular", "palatina"]
SITIOS = [0, 1, 2]           # mesial / central / distal, en el orden que se ve


def _filas(paciente):
    es_nino = (paciente.get("tipo_paciente") or "adulto") == "nino"
    if es_nino:
        return FILA_SUPERIOR_NINO, FILA_INFERIOR_NINO
    return FILA_SUPERIOR_ADULTO, FILA_INFERIOR_ADULTO


# ---------------------------------------------------------------------
# Estructura de datos
# ---------------------------------------------------------------------

def _cara_vacia() -> dict:
    return {
        "furca": "",
        "anchura": None,
        "sangrado": [False, False, False],
        "supuracion": [False, False, False],
        "placa": [False, False, False],
        "margen": [None, None, None],
        "sondaje": [None, None, None],
    }


def _pieza_vacia() -> dict:
    return {
        "ausencia": False, "implante": False, "movilidad": "", "pronostico": "",
        "vestibular": _cara_vacia(), "palatina": _cara_vacia(),
    }


def _normalizar(guardado: dict, piezas: list) -> dict:
    """Completa la estructura para que toda pieza tenga sus 2 caras y 3 sitios."""
    completo = {}
    for fdi in piezas:
        base = _pieza_vacia()
        entrada = (guardado or {}).get(str(fdi))
        if entrada:
            for campo in ("ausencia", "implante", "movilidad", "pronostico"):
                if campo in entrada:
                    base[campo] = entrada[campo]
            for cara in CARAS:
                origen = entrada.get(cara) or {}
                destino = base[cara]
                for campo in ("furca", "anchura"):
                    if campo in origen:
                        destino[campo] = origen[campo]
                for campo in ("sangrado", "supuracion", "placa", "margen", "sondaje"):
                    valores = origen.get(campo)
                    if isinstance(valores, list):
                        for i in SITIOS:
                            if i < len(valores):
                                destino[campo][i] = valores[i]
        completo[fdi] = base
    return completo


def _entero(valor):
    valor = (valor or "").strip()
    if not valor:
        return None
    try:
        return int(valor)
    except ValueError:
        return None


def _leer_formulario(piezas: list) -> dict:
    """Arma el dict de datos a partir del POST, omitiendo piezas sin nada."""
    datos = {}
    for fdi in piezas:
        pieza = {
            "ausencia": request.form.get(f"ausencia_{fdi}") == "on",
            "implante": request.form.get(f"implante_{fdi}") == "on",
            "movilidad": (request.form.get(f"movilidad_{fdi}") or "").strip(),
            "pronostico": (request.form.get(f"pronostico_{fdi}") or "").strip(),
        }
        con_datos = pieza["ausencia"] or pieza["implante"] or pieza["movilidad"] or pieza["pronostico"]

        for cara in CARAS:
            sufijo = f"{fdi}_{cara}"
            c = {
                "furca": (request.form.get(f"furca_{sufijo}") or "").strip(),
                "anchura": _entero(request.form.get(f"anchura_{sufijo}")),
                "sangrado": [request.form.get(f"sangrado_{sufijo}_{i}") == "on" for i in SITIOS],
                "supuracion": [request.form.get(f"supuracion_{sufijo}_{i}") == "on" for i in SITIOS],
                "placa": [request.form.get(f"placa_{sufijo}_{i}") == "on" for i in SITIOS],
                "margen": [_entero(request.form.get(f"margen_{sufijo}_{i}")) for i in SITIOS],
                "sondaje": [_entero(request.form.get(f"sondaje_{sufijo}_{i}")) for i in SITIOS],
            }
            pieza[cara] = c
            if (c["furca"] or c["anchura"] is not None or any(c["sangrado"]) or any(c["supuracion"])
                    or any(c["placa"]) or any(v is not None for v in c["margen"])
                    or any(v is not None for v in c["sondaje"])):
                con_datos = True

        if con_datos:
            datos[str(fdi)] = pieza
    return datos


def _resumen(datos: dict, piezas: list) -> dict:
    """
    %Placa y %SAS sobre los sitios de piezas presentes, media de profundidad
    de sondaje y media de nivel de inserción clínica (NIC = sondaje + margen).
    """
    sitios = con_placa = con_sangrado = con_supuracion = 0
    sondajes, nics = [], []

    for fdi in piezas:
        pieza = (datos or {}).get(str(fdi))
        if pieza and pieza.get("ausencia"):
            continue                       # una pieza ausente no aporta sitios
        sitios += len(CARAS) * len(SITIOS)
        if not pieza:
            continue
        for cara in CARAS:
            c = pieza.get(cara) or {}
            for i in SITIOS:
                con_placa += bool((c.get("placa") or [])[i:i + 1] and c["placa"][i])
                con_sangrado += bool((c.get("sangrado") or [])[i:i + 1] and c["sangrado"][i])
                con_supuracion += bool((c.get("supuracion") or [])[i:i + 1] and c["supuracion"][i])
                sondaje = (c.get("sondaje") or [None, None, None])[i]
                if sondaje is not None:
                    sondajes.append(sondaje)
                    margen = (c.get("margen") or [None, None, None])[i] or 0
                    nics.append(sondaje + margen)

    pct = lambda n: round(n / sitios * 100, 2) if sitios else 0
    media = lambda xs: round(sum(xs) / len(xs), 2) if xs else 0
    return {
        "indice_placa": pct(con_placa),
        "indice_sangrado": pct(con_sangrado),
        "sitios_supuracion": con_supuracion,
        "media_sondaje": media(sondajes),
        "media_nic": media(nics),
    }


# ---------------------------------------------------------------------
# Dibujo de los dientes (coordenadas normalizadas por celda)
# ---------------------------------------------------------------------

ANCHO_DIENTE = 40
ALTO_DIENTE = 92
CEJ_Y = 50                    # línea amelocementaria: origen de las medidas
ESCALA_MM = 3.0               # px por milímetro
SITIOS_X = [8, 20, 32]

# Contornos dibujados con la corona abajo y la(s) raíz(es) hacia arriba.
# La fila espejada reutiliza los mismos trazos con un scale(1,-1).
CORONAS = {
    "molar":    "M5,50 L5,70 Q5,84 11,86 L29,86 Q35,84 35,70 L35,50 Z",
    "premolar": "M8,50 L8,70 Q8,83 13,85 L27,85 Q32,83 32,70 L32,50 Z",
    "canino":   "M10,50 L10,68 Q10,78 20,88 Q30,78 30,68 L30,50 Z",
    "incisivo": "M11,50 L11,74 Q11,84 20,86 Q29,84 29,74 L29,50 Z",
}
RAICES = {
    ("molar", 3): [
        "M5,50 L15,50 Q13,28 10,9 Q6,28 5,50 Z",
        "M16,50 L24,50 Q22,28 20,7 Q18,28 16,50 Z",
        "M25,50 L35,50 Q34,28 30,9 Q27,28 25,50 Z",
    ],
    ("molar", 2): [
        "M5,50 L18,50 Q15,28 11,9 Q6,28 5,50 Z",
        "M22,50 L35,50 Q34,28 29,9 Q25,28 22,50 Z",
    ],
    ("premolar", 1): ["M12,50 L28,50 Q26,26 20,6 Q14,26 12,50 Z"],
    ("canino", 1):   ["M12,50 L28,50 Q27,24 20,4 Q13,24 12,50 Z"],
    ("incisivo", 1): ["M13,50 L27,50 Q26,28 20,8 Q14,28 13,50 Z"],
}


def _tipo_diente(fdi: int) -> str:
    pos = fdi % 10
    if fdi // 10 in (5, 6, 7, 8):
        # Dentición temporal: las piezas 4 y 5 son molares, no premolares.
        return "molar" if pos in (4, 5) else ("canino" if pos == 3 else "incisivo")
    if pos in (6, 7, 8):
        return "molar"
    if pos in (4, 5):
        return "premolar"
    if pos == 3:
        return "canino"
    return "incisivo"


def _es_superior(fdi: int) -> bool:
    return fdi // 10 in (1, 2, 5, 6)


def _geometria_cara(cara: dict) -> dict:
    """
    Convierte margen y sondaje (mm) en las polilíneas del dibujo.
    El margen sube (dirección apical = y menor) cuando hay recesión, y el
    fondo de bolsa cuelga otro tanto por debajo según la profundidad.
    """
    puntos = []
    for i, x in enumerate(SITIOS_X):
        margen = cara["margen"][i] or 0
        sondaje = cara["sondaje"][i] or 0
        y_margen = CEJ_Y - margen * ESCALA_MM
        puntos.append({"x": x, "ym": y_margen, "yf": y_margen - sondaje * ESCALA_MM})

    linea_margen = " ".join(f"{p['x']},{p['ym']}" for p in puntos)
    linea_fondo = " ".join(f"{p['x']},{p['yf']}" for p in puntos)
    area = linea_margen + " " + " ".join(f"{p['x']},{p['yf']}" for p in reversed(puntos))
    return {"margen": linea_margen, "fondo": linea_fondo, "area": area}


def _dientes(piezas: list, datos: dict) -> list:
    dibujos = []
    for fdi in piezas:
        tipo = _tipo_diente(fdi)
        n_raices = 3 if (tipo == "molar" and _es_superior(fdi)) else (2 if tipo == "molar" else 1)
        pieza = datos[fdi]
        dibujos.append({
            "fdi": fdi,
            "corona": CORONAS[tipo],
            "raices": RAICES[(tipo, n_raices)],
            "ausencia": pieza["ausencia"],
            "implante": pieza["implante"],
            "geo_vestibular": _geometria_cara(pieza["vestibular"]),
            "geo_palatina": _geometria_cara(pieza["palatina"]),
        })
    return dibujos


# ---------------------------------------------------------------------
# Vistas
# ---------------------------------------------------------------------

def _contexto(paciente, datos, registro=None):
    fila_superior, fila_inferior = _filas(paciente)
    return {
        "paciente": paciente,
        "p": registro,
        "fila_superior": fila_superior,
        "fila_inferior": fila_inferior,
        "medio_superior": len(fila_superior) // 2,
        "medio_inferior": len(fila_inferior) // 2,
        "datos": datos,
        "dientes_superior": _dientes(fila_superior, datos),
        "dientes_inferior": _dientes(fila_inferior, datos),
        "sitios": SITIOS,
        "resumen": _resumen(
            {str(k): v for k, v in datos.items()}, fila_superior + fila_inferior
        ),
    }


@bp.route("/pacientes/<int:paciente_id>/nuevo", methods=["GET", "POST"])
def nuevo(paciente_id):
    paciente = _obtener_paciente(paciente_id)
    fila_superior, fila_inferior = _filas(paciente)
    piezas = fila_superior + fila_inferior

    if request.method == "POST":
        datos = _leer_formulario(piezas)
        resumen = _resumen(datos, piezas)
        creado = sb.table("periodontogramas").insert({
            "paciente_id": paciente_id,
            "datos": datos,
            "notas": (request.form.get("notas") or "").strip() or None,
            **resumen,
        }).execute().data
        flash(f"Periodontograma guardado — placa {resumen['indice_placa']}% · "
              f"sangrado {resumen['indice_sangrado']}%.", "success")
        return redirect(url_for("periodontograma.ver", periodontograma_id=creado[0]["id"]))

    return render_template(
        "periodontograma/carta.html",
        **_contexto(paciente, _normalizar({}, piezas)),
        accion=url_for("periodontograma.nuevo", paciente_id=paciente_id),
        notas="",
    )


@bp.route("/<int:periodontograma_id>", methods=["GET", "POST"])
def ver(periodontograma_id):
    fila = sb.table("periodontogramas").select("*").eq("id", periodontograma_id).limit(1).execute().data
    if not fila:
        abort(404)
    registro = fila[0]
    paciente = _obtener_paciente(registro["paciente_id"])
    fila_superior, fila_inferior = _filas(paciente)
    piezas = fila_superior + fila_inferior

    if request.method == "POST":
        datos = _leer_formulario(piezas)
        resumen = _resumen(datos, piezas)
        sb.table("periodontogramas").update({
            "datos": datos,
            "notas": (request.form.get("notas") or "").strip() or None,
            **resumen,
        }).eq("id", periodontograma_id).execute()
        flash("Periodontograma actualizado.", "success")
        return redirect(url_for("periodontograma.ver", periodontograma_id=periodontograma_id))

    return render_template(
        "periodontograma/carta.html",
        **_contexto(paciente, _normalizar(registro.get("datos") or {}, piezas), registro),
        accion=url_for("periodontograma.ver", periodontograma_id=periodontograma_id),
        notas=registro.get("notas") or "",
    )


@bp.route("/<int:periodontograma_id>/eliminar", methods=["POST"])
def eliminar(periodontograma_id):
    fila = sb.table("periodontogramas").select("paciente_id").eq("id", periodontograma_id).limit(1).execute().data
    if not fila:
        abort(404)
    sb.table("periodontogramas").delete().eq("id", periodontograma_id).execute()
    flash("Periodontograma eliminado.", "info")
    return redirect(url_for("pacientes.detalle", paciente_id=fila[0]["paciente_id"]))


def _obtener_paciente(paciente_id: int) -> dict:
    resp = sb.table("pacientes").select("*").eq("id", paciente_id).limit(1).execute()
    if not resp.data:
        abort(404)
    return resp.data[0]
