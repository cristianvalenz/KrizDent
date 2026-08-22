"""
API del odontograma.

El diagrama se dibuja en el navegador (static/js/odontograma.js) y cada clic
manda un POST con la pieza y su nuevo estado. Se responde JSON, no HTML,
para que la página no se recargue mientras el odontólogo marca piezas.

Hay dos niveles de estado:
  - Pieza completa (tabla "odontograma"): sano, ausente, corona.
  - Por cara (tabla "odontograma_caras"): sano, caries, obturado — una
    caries u obturación se documenta en la cara donde está, no en toda
    la pieza.
"""

from flask import Blueprint, abort, jsonify, request

from services.constantes import (ARCADAS, CARAS_PIEZA, ESTADOS_CARA,
                                  ESTADOS_ORTODONCIA, ESTADOS_PIEZA,
                                  TIPOS_ORTODONCIA)
from services.supabase_client import sb

bp = Blueprint("odontograma", __name__, url_prefix="/odontograma")

# Numeración FDI: 32 piezas permanentes (adulto) + 20 piezas temporales (niño).
# Se acepta la unión de ambas para no tener que distinguir el tipo de paciente
# aquí — el frontend ya solo dibuja y envía las que corresponden.
PIEZAS_VALIDAS = {
    *range(11, 19), *range(21, 29), *range(31, 39), *range(41, 49),
    *range(51, 56), *range(61, 66), *range(71, 76), *range(81, 86),
}


@bp.route("/<int:paciente_id>", methods=["GET"])
def obtener(paciente_id):
    """Devuelve {"11": {"estado": "caries", "perno": false}, ...} para pintar el diagrama."""
    filas = (
        sb.table("odontograma").select("pieza, estado, con_perno")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    return jsonify({
        str(f["pieza"]): {"estado": f["estado"], "perno": f["con_perno"]} for f in filas
    })


@bp.route("/<int:paciente_id>", methods=["POST"])
def guardar(paciente_id):
    """
    Guarda el estado de una pieza completa. Body JSON: {"pieza": 36, "estado": "ausente"}

    Usa upsert sobre la restricción unique(paciente_id, pieza): si la pieza ya
    tenía un registro lo actualiza, y si no, lo crea. Una sola llamada a la BD.
    """
    datos = request.get_json(silent=True) or {}

    try:
        pieza = int(datos.get("pieza"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Pieza inválida."}), 400

    estado = datos.get("estado")

    if pieza not in PIEZAS_VALIDAS:
        return jsonify({"ok": False, "error": f"La pieza {pieza} no existe en notación FDI."}), 400
    if estado not in ESTADOS_PIEZA:
        return jsonify({"ok": False, "error": f"El estado «{estado}» no está permitido."}), 400

    sb.table("odontograma").upsert(
        {"paciente_id": paciente_id, "pieza": pieza, "estado": estado},
        on_conflict="paciente_id,pieza",
    ).execute()

    return jsonify({"ok": True, "pieza": pieza, "estado": estado})


@bp.route("/<int:paciente_id>/perno", methods=["POST"])
def guardar_perno(paciente_id):
    """
    Marca o desmarca el perno de una pieza. Body JSON: {"pieza": 36, "perno": true}

    Es independiente del "estado": una pieza puede tener perno sin corona
    (a la espera de una) o corona sin perno.
    """
    datos = request.get_json(silent=True) or {}

    try:
        pieza = int(datos.get("pieza"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Pieza inválida."}), 400

    if pieza not in PIEZAS_VALIDAS:
        return jsonify({"ok": False, "error": f"La pieza {pieza} no existe en notación FDI."}), 400

    perno = bool(datos.get("perno"))

    existente = (
        sb.table("odontograma").select("estado").eq("paciente_id", paciente_id)
        .eq("pieza", pieza).limit(1).execute().data
    )
    estado_actual = existente[0]["estado"] if existente else "sano"

    sb.table("odontograma").upsert(
        {"paciente_id": paciente_id, "pieza": pieza, "estado": estado_actual, "con_perno": perno},
        on_conflict="paciente_id,pieza",
    ).execute()

    return jsonify({"ok": True, "pieza": pieza, "perno": perno})


@bp.route("/<int:paciente_id>/caras", methods=["GET"])
def obtener_caras(paciente_id):
    """Devuelve {"36": {"oclusal": "caries", "mesial": "obturado"}, ...}."""
    filas = (
        sb.table("odontograma_caras").select("pieza, cara, estado")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    resultado: dict = {}
    for f in filas:
        resultado.setdefault(str(f["pieza"]), {})[f["cara"]] = f["estado"]
    return jsonify(resultado)


@bp.route("/<int:paciente_id>/cara", methods=["POST"])
def guardar_cara(paciente_id):
    """
    Guarda el estado de una cara. Body JSON: {"pieza": 36, "cara": "oclusal", "estado": "caries"}
    """
    datos = request.get_json(silent=True) or {}

    try:
        pieza = int(datos.get("pieza"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Pieza inválida."}), 400

    cara = datos.get("cara")
    estado = datos.get("estado")

    if pieza not in PIEZAS_VALIDAS:
        return jsonify({"ok": False, "error": f"La pieza {pieza} no existe en notación FDI."}), 400
    if cara not in CARAS_PIEZA:
        return jsonify({"ok": False, "error": f"La cara «{cara}» no existe."}), 400
    if estado not in ESTADOS_CARA:
        return jsonify({"ok": False, "error": f"El estado «{estado}» no está permitido en una cara."}), 400

    sb.table("odontograma_caras").upsert(
        {"paciente_id": paciente_id, "pieza": pieza, "cara": cara, "estado": estado},
        on_conflict="paciente_id,pieza,cara",
    ).execute()

    return jsonify({"ok": True, "pieza": pieza, "cara": cara, "estado": estado})


@bp.route("/<int:paciente_id>/reiniciar", methods=["POST"])
def reiniciar(paciente_id):
    """Deja todas las piezas y caras en 'sano' borrando los registros del paciente."""
    sb.table("odontograma").delete().eq("paciente_id", paciente_id).execute()
    sb.table("odontograma_caras").delete().eq("paciente_id", paciente_id).execute()
    return jsonify({"ok": True})


@bp.route("/<int:paciente_id>/ortodoncia", methods=["GET"])
def obtener_ortodoncia(paciente_id):
    """Lista los aparatos de ortodoncia del paciente (normalmente 0 o 1, pero
    nada impide tener uno fijo arriba y uno removible abajo a la vez)."""
    filas = (
        sb.table("ortodoncia_aparatos").select("*")
        .eq("paciente_id", paciente_id).order("id").execute().data or []
    )
    return jsonify(filas)


@bp.route("/<int:paciente_id>/ortodoncia", methods=["POST"])
def guardar_ortodoncia(paciente_id):
    """
    Registra un aparato de ortodoncia.
    Fijo:      {"tipo": "fijo", "estado": "bueno", "pieza_desde": 16, "pieza_hasta": 26}
    Removible: {"tipo": "removible", "estado": "bueno", "arcada": "superior"}
    """
    datos = request.get_json(silent=True) or {}
    tipo = datos.get("tipo")
    estado = datos.get("estado", "bueno")

    if tipo not in TIPOS_ORTODONCIA:
        return jsonify({"ok": False, "error": f"Tipo de aparato «{tipo}» no reconocido."}), 400
    if estado not in ESTADOS_ORTODONCIA:
        return jsonify({"ok": False, "error": f"Estado «{estado}» no reconocido."}), 400

    fila = {"paciente_id": paciente_id, "tipo": tipo, "estado": estado}

    if tipo == "fijo":
        try:
            desde = int(datos.get("pieza_desde"))
            hasta = int(datos.get("pieza_hasta"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Elige las dos piezas extremas del aparato."}), 400
        if desde not in PIEZAS_VALIDAS or hasta not in PIEZAS_VALIDAS:
            return jsonify({"ok": False, "error": "Pieza inválida."}), 400
        fila["pieza_desde"] = desde
        fila["pieza_hasta"] = hasta
    else:
        arcada = datos.get("arcada")
        if arcada not in ARCADAS:
            return jsonify({"ok": False, "error": "Elige la arcada (superior o inferior)."}), 400
        fila["arcada"] = arcada

    creado = sb.table("ortodoncia_aparatos").insert(fila).execute().data[0]
    return jsonify({"ok": True, "aparato": creado})


@bp.route("/ortodoncia/<int:aparato_id>", methods=["DELETE"])
def eliminar_ortodoncia(aparato_id):
    sb.table("ortodoncia_aparatos").delete().eq("id", aparato_id).execute()
    return jsonify({"ok": True})


# -----------------------------------------------------------------------
# Versiones del odontograma: "Inicial" y "Alta" son fotos congeladas de un
# momento puntual; "Evolución" es simplemente el estado vivo de arriba
# (las tablas odontograma/odontograma_caras), no necesita nada especial.
# -----------------------------------------------------------------------
@bp.route("/<int:paciente_id>/version/<tipo>", methods=["GET"])
def obtener_version(paciente_id, tipo):
    if tipo not in ("inicial", "alta"):
        abort(400)
    fila = (
        sb.table("odontograma_versiones").select("*")
        .eq("paciente_id", paciente_id).eq("tipo", tipo).limit(1).execute().data
    )
    if not fila:
        return jsonify(None)
    return jsonify(fila[0])


@bp.route("/<int:paciente_id>/version/<tipo>", methods=["POST"])
def guardar_version(paciente_id, tipo):
    """Congela el estado ACTUAL del odontograma como 'inicial' o 'alta'."""
    if tipo not in ("inicial", "alta"):
        abort(400)

    filas = (
        sb.table("odontograma").select("pieza, estado, con_perno")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    odontograma_actual = {str(f["pieza"]): {"estado": f["estado"], "perno": f["con_perno"]} for f in filas}

    filas_caras = (
        sb.table("odontograma_caras").select("pieza, cara, estado")
        .eq("paciente_id", paciente_id).execute().data or []
    )
    caras_actual: dict = {}
    for f in filas_caras:
        caras_actual.setdefault(str(f["pieza"]), {})[f["cara"]] = f["estado"]

    ortodoncia_actual = (
        sb.table("ortodoncia_aparatos").select("*")
        .eq("paciente_id", paciente_id).execute().data or []
    )

    creado = sb.table("odontograma_versiones").upsert({
        "paciente_id": paciente_id,
        "tipo": tipo,
        "odontograma": odontograma_actual,
        "odontograma_caras": caras_actual,
        "ortodoncia": ortodoncia_actual,
    }, on_conflict="paciente_id,tipo").execute().data[0]

    return jsonify({"ok": True, "version": creado})
