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


def subir_bytes(contenido: bytes, ruta: str, content_type: str) -> str:
    """
    Sube bytes ya en memoria (ej. una firma capturada en <canvas>, exportada
    como PNG) y devuelve la URL pública. Más genérico que subir_imagen():
    ese requiere un FileStorage de un <input type=file>.
    """
    if not contenido:
        raise ErrorSubida("El archivo llegó vacío.")
    try:
        sb.storage.from_(BUCKET).upload(
            path=ruta, file=contenido,
            file_options={"content-type": content_type, "upsert": "false"},
        )
    except Exception as e:
        raise ErrorSubida(f"Storage rechazó el archivo: {e}") from e
    return sb.storage.from_(BUCKET).get_public_url(ruta)


def subir_logo(archivo, clinica_id: int) -> dict:
    """
    Sube el logo de una clínica y devuelve {"url": ..., "storage_path": ...}.

    Va aparte de subir_imagen() porque un logo no cuelga de ningún paciente y
    acepta SVG además de los formatos de foto: muchas clínicas tienen su marca
    en vectorial y perdería nitidez convertida a mapa de bits.
    """
    nombre_orig = archivo.filename or "logo"
    ext = os.path.splitext(nombre_orig)[1].lower()

    permitidas = EXT_IMAGEN | {".svg"}
    if ext not in permitidas:
        raise ErrorSubida(
            f"«{nombre_orig}» no es una imagen válida. "
            f"Formatos aceptados: {', '.join(sorted(permitidas))}."
        )

    contenido = archivo.read()
    if not contenido:
        raise ErrorSubida(f"«{nombre_orig}» llegó vacío. Vuelve a seleccionarlo.")

    # El UUID hace que el navegador no siga mostrando el logo viejo en caché
    # cuando se reemplaza.
    storage_path = f"clinicas/{clinica_id}/{uuid.uuid4().hex}{ext}"
    content_type = ("image/svg+xml" if ext == ".svg"
                    else mimetypes.guess_type(nombre_orig)[0] or "application/octet-stream")

    try:
        sb.storage.from_(BUCKET).upload(
            path=storage_path, file=contenido,
            file_options={"content-type": content_type, "upsert": "false"},
        )
    except Exception as e:
        raise ErrorSubida(
            f"Storage rechazó «{nombre_orig}»: {e}. "
            f"Verifica que el bucket «{BUCKET}» exista y sea público."
        ) from e

    return {
        "storage_path": storage_path,
        "url": sb.storage.from_(BUCKET).get_public_url(storage_path),
    }
