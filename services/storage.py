"""
Subida de imágenes (radiografías, fotos intraorales) a Supabase Storage.

El archivo binario vive en el bucket; en la base de datos solo guardamos
la ruta y la URL. Así la tabla se mantiene liviana y rápida.
"""

import mimetypes
import os
import uuid

from services.constantes import EXT_IMAGEN
from services.supabase_client import BUCKET, sb


class ErrorSubida(Exception):
    """Se lanza cuando el archivo no es válido o Storage rechaza la subida."""


def subir_imagen(archivo, paciente_id: int) -> dict:
    """
    Sube un FileStorage de Flask al bucket y devuelve los datos para guardar en BD.

    Devuelve: {"storage_path": ..., "url": ..., "nombre_orig": ...}
    Lanza ErrorSubida si la extensión no está permitida o falla el envío.
    """
    nombre_orig = archivo.filename or "imagen"
    ext = os.path.splitext(nombre_orig)[1].lower()

    if ext not in EXT_IMAGEN:
        permitidas = ", ".join(sorted(EXT_IMAGEN))
        raise ErrorSubida(
            f"«{nombre_orig}» no es una imagen válida. Formatos aceptados: {permitidas}."
        )

    # Ruta única dentro del bucket: pacientes/12/uuid.jpg
    # El UUID evita que dos archivos con el mismo nombre se pisen.
    storage_path = f"pacientes/{paciente_id}/{uuid.uuid4().hex}{ext}"
    contenido = archivo.read()

    if not contenido:
        raise ErrorSubida(f"«{nombre_orig}» llegó vacío. Vuelve a seleccionarlo.")

    content_type = mimetypes.guess_type(nombre_orig)[0] or "application/octet-stream"

    try:
        sb.storage.from_(BUCKET).upload(
            path=storage_path,
            file=contenido,
            file_options={"content-type": content_type, "upsert": "false"},
        )
    except Exception as e:  # supabase-py envuelve los errores HTTP
        raise ErrorSubida(
            f"Storage rechazó «{nombre_orig}»: {e}. "
            f"Verifica que el bucket «{BUCKET}» exista y sea público."
        ) from e

    url = sb.storage.from_(BUCKET).get_public_url(storage_path)

    return {"storage_path": storage_path, "url": url, "nombre_orig": nombre_orig}


def borrar_imagen(storage_path: str) -> None:
    """Elimina el archivo del bucket. Silencioso si ya no existe."""
    try:
        sb.storage.from_(BUCKET).remove([storage_path])
    except Exception:
        pass
