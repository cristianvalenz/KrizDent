"""
KrizDent — Sistema de gestión para centro odontológico.

Punto de entrada de la aplicación Flask.
Ejecutar con:  python app.py
"""

import os

from dotenv import load_dotenv
from flask import Flask, render_template

# Carga las variables del archivo .env ANTES de importar cualquier módulo
# que las necesite (services/supabase_client.py lee SUPABASE_URL al importarse).
load_dotenv()

from routes.almacen import bp as almacen_bp                # noqa: E402
from routes.citas import bp as citas_bp                    # noqa: E402
from routes.consentimientos import bp as consentimientos_bp  # noqa: E402
from routes.dashboard import bp as dashboard_bp            # noqa: E402
from routes.finanzas import bp as finanzas_bp              # noqa: E402
from routes.historial import bp as historial_bp            # noqa: E402
from routes.laboratorio import bp as laboratorio_bp        # noqa: E402
from routes.odontograma import bp as odont_bp              # noqa: E402
from routes.pacientes import bp as pacientes_bp            # noqa: E402
from routes.periodontograma import bp as periodontograma_bp  # noqa: E402
from routes.profesionales import bp as profesionales_bp    # noqa: E402
from routes.recetas import bp as recetas_bp                # noqa: E402
from routes.reportes import bp as reportes_bp              # noqa: E402
from services.filtros import registrar_filtros             # noqa: E402


def crear_app() -> Flask:
    """Construye y configura la instancia de Flask (patrón application factory)."""
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-inseguro-cambiar")
    # Límite de subida: 8 MB por archivo. Una radiografía panorámica JPG pesa ~1-3 MB.
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

    # Filtros Jinja propios: |fecha, |hora, |edad, etc.
    registrar_filtros(app)

    # Cada módulo del sistema vive en su propio blueprint.
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pacientes_bp)
    app.register_blueprint(citas_bp)
    app.register_blueprint(historial_bp)
    app.register_blueprint(odont_bp)
    app.register_blueprint(recetas_bp)
    app.register_blueprint(almacen_bp)
    app.register_blueprint(finanzas_bp)
    app.register_blueprint(laboratorio_bp)
    app.register_blueprint(consentimientos_bp)
    app.register_blueprint(reportes_bp)
    app.register_blueprint(periodontograma_bp)
    app.register_blueprint(profesionales_bp)

    # ---- Manejo de errores ------------------------------------------------
    @app.errorhandler(404)
    def no_encontrado(_e):
        return render_template(
            "error.html",
            codigo=404,
            titulo="Esa página no existe",
            detalle="Revisa el enlace o vuelve al panel principal.",
        ), 404

    @app.errorhandler(413)
    def archivo_muy_grande(_e):
        return render_template(
            "error.html",
            codigo=413,
            titulo="El archivo pesa demasiado",
            detalle="El límite por imagen es 8 MB. Reduce la resolución e inténtalo otra vez.",
        ), 413

    @app.errorhandler(500)
    def error_interno(_e):
        return render_template(
            "error.html",
            codigo=500,
            titulo="Algo falló en el servidor",
            detalle="Revisa la consola donde corre Flask para ver el detalle técnico.",
        ), 500

    return app


app = crear_app()


if __name__ == "__main__":
    # host="0.0.0.0" permite que la segunda persona del consultorio entre
    # desde otra PC de la misma red usando http://IP-DE-ESTA-PC:5000
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
