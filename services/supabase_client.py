"""
Conexión única a Supabase.

Se crea un solo cliente al importar el módulo y se reutiliza en toda la app
(supabase-py maneja internamente el pool de conexiones HTTP).
"""

import os

from supabase import Client, create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
BUCKET = os.getenv("SUPABASE_BUCKET", "historial").strip()

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Faltan SUPABASE_URL o SUPABASE_KEY. "
        "Copia .env.example como .env y completa los valores de tu proyecto."
    )

# Cliente compartido. Se importa así:  from services.supabase_client import sb
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
