"""
La cara pública: la página de presentación de DentalSIS.

Vive en la raíz del mismo dominio que el sistema. Así el botón «Ingresar»
apunta siempre al login correcto sin importar dónde esté desplegado, y hay
un solo despliegue en vez de una web de marketing por un lado y la
aplicación por otro.

Quien ya tiene sesión abierta no ve la presentación: se le manda directo a
su panel, como en cualquier sistema que se usa a diario.
"""

import os

from flask import Blueprint, redirect, send_from_directory, url_for

from services.auth import modulos_visibles, usuario_actual

bp = Blueprint("publico", __name__)

CARPETA = os.path.join(os.path.dirname(__file__), "..", "landing")

# A dónde entra cada quien según lo que tenga contratado. Duplica la tabla de
# routes/auth.py a propósito acotada: aquí solo hace falta el primer destino.
INICIO = {
    "panel":         "dashboard.index",
    "pacientes":     "pacientes.lista",
    "agenda":        "citas.lista",
    "presupuestos":  "finanzas.lista",
    "recetas":       "recetas.lista",
    "almacen":       "almacen.lista",
    "reportes":      "reportes.index",
    "profesionales": "profesionales.lista",
}


@bp.route("/")
def inicio():
    usuario = usuario_actual()

    if usuario:
        if usuario["rol"] == "superadmin":
            return redirect(url_for("admin.clinicas"))
        for modulo in modulos_visibles():
            if modulo in INICIO:
                return redirect(url_for(INICIO[modulo]))
        return redirect(url_for("auth.perfil"))

    # El archivo se sirve tal cual, sin plantilla: es HTML autocontenido y así
    # el mismo archivo sirve para publicarlo aparte si algún día hace falta.
    return send_from_directory(CARPETA, "index.html")
