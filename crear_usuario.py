"""
Crea o actualiza una cuenta desde la terminal.

Sirve para dar de alta al primer superadministrador (que no se puede crear
desde la web, porque para entrar a la web hace falta una cuenta) y para
recuperar el acceso si alguien olvida su contraseña y no hay nadie más.

Ejemplos:
    python crear_usuario.py --superadmin admin@krizdent.com "Cristian" 12345
    python crear_usuario.py --clinica krizdent correo@ejemplo.com "Nombre" 12345
    python crear_usuario.py --clave correo@ejemplo.com nueva-clave
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from services.auth import hashear          # noqa: E402
from services.constantes import MODULOS    # noqa: E402
from services.supabase_client import sb    # noqa: E402


def _existente(email: str):
    filas = sb.table("usuarios").select("*").ilike("email", email).limit(1).execute().data
    return filas[0] if filas else None


def _guardar(email: str, nombre: str, clave: str, clinica_id, rol: str) -> None:
    datos = {
        "clinica_id": clinica_id,
        "nombre": nombre,
        "email": email.lower(),
        "password_hash": hashear(clave),
        "rol": rol,
        "modulos": [] if rol == "superadmin" else list(MODULOS),
        "activo": True,
    }
    previo = _existente(email)
    if previo:
        sb.table("usuarios").update(datos).eq("id", previo["id"]).execute()
        print(f"Actualizado: {email} ({rol})")
    else:
        sb.table("usuarios").insert(datos).execute()
        print(f"Creado: {email} ({rol})")
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
        usuario = _existente(argv[2])
        if not usuario:
            print(f"No existe la cuenta {argv[2]}.")
            return 1
        sb.table("usuarios").update(
            {"password_hash": hashear(argv[3])}
        ).eq("id", usuario["id"]).execute()
        print(f"Contraseña de {argv[2]} cambiada a: {argv[3]}")

    else:
        print(__doc__)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
