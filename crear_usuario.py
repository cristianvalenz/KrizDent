"""
Crea o actualiza una cuenta desde la terminal.

Sirve para dar de alta al primer superadministrador (que no se puede crear
desde la web, porque para entrar a la web hace falta una cuenta) y para
recuperar el acceso si alguien olvida su contraseña y no hay nadie más.

Al sistema se entra con el NOMBRE DE USUARIO, no con el correo. El correo
es opcional y solo se guarda para recuperar la clave y mandar avisos.

Ejemplos:
    python crear_usuario.py --superadmin Admin "Cristian" 12345
    python crear_usuario.py --clinica krizdent krizdent "KrizDent" 12345
    python crear_usuario.py --clave Admin nueva-clave
    python crear_usuario.py --correo Admin correo@ejemplo.com
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from services.auth import hashear          # noqa: E402
from services.constantes import MODULOS    # noqa: E402
from services.supabase_client import sb    # noqa: E402


def _buscar(acceso: str):
    """Busca por usuario, sin distinguir mayúsculas (igual que al entrar)."""
    filas = sb.table("usuarios").select("*").ilike("usuario", acceso).limit(1).execute().data
    return filas[0] if filas else None


def _guardar(acceso: str, nombre: str, clave: str, clinica_id, rol: str) -> None:
    datos = {
        "clinica_id": clinica_id,
        "usuario": acceso,
        "nombre": nombre,
        "password_hash": hashear(clave),
        "rol": rol,
        "modulos": [] if rol == "superadmin" else list(MODULOS),
        "activo": True,
    }
    previo = _buscar(acceso)
    if previo:
        sb.table("usuarios").update(datos).eq("id", previo["id"]).execute()
        print(f"Actualizado: {acceso} ({rol})")
    else:
        sb.table("usuarios").insert(datos).execute()
        print(f"Creado: {acceso} ({rol})")
    print(f"Contraseña: {clave}")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1

    modo = argv[1]

    if modo == "--superadmin" and len(argv) == 5:
        _guardar(argv[2], argv[3], argv[4], None, "superadmin")

    elif modo == "--clinica" and len(argv) == 6:
        slug = argv[2]
        filas = sb.table("clinicas").select("id, nombre").eq("slug", slug).limit(1).execute().data
        if not filas:
            print(f"No existe ninguna clínica con slug '{slug}'.")
            return 1
        _guardar(argv[3], argv[4], argv[5], filas[0]["id"], "dueno")
        print(f"Clínica: {filas[0]['nombre']}")

    elif modo == "--clave" and len(argv) == 4:
        usuario = _buscar(argv[2])
        if not usuario:
            print(f"No existe la cuenta '{argv[2]}'.")
            return 1
        sb.table("usuarios").update(
            {"password_hash": hashear(argv[3])}
        ).eq("id", usuario["id"]).execute()
        print(f"Contraseña de '{argv[2]}' cambiada a: {argv[3]}")

    elif modo == "--correo" and len(argv) == 4:
        usuario = _buscar(argv[2])
        if not usuario:
            print(f"No existe la cuenta '{argv[2]}'.")
            return 1
        sb.table("usuarios").update(
            {"email": argv[3].strip().lower() or None}
        ).eq("id", usuario["id"]).execute()
        print(f"Correo de '{argv[2]}' actualizado a: {argv[3]}")

    else:
        print(__doc__)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
