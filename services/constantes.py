"""Valores fijos del dominio. Mantener sincronizados con los CHECK de schema.sql."""

# --- Datos de la clínica (para el encabezado del PDF de receta) -----------
CLINICA = {
    "nombre": "KrizDent",
    "eslogan": "Sonrisas sanas y brillantes",
    "celular": "900181998",
    "direccion": "Santa Cruz de Cajamarquilla, MZ D lote 5",
}

# --- Citas -----------------------------------------------------------------
ESTADOS_CITA = {
    "pendiente":  {"etiqueta": "Pendiente",  "clase": "estado-pendiente"},
    "completada": {"etiqueta": "Completada", "clase": "estado-completada"},
    "cancelada":  {"etiqueta": "Cancelada",  "clase": "estado-cancelada"},
}

# --- Odontograma -----------------------------------------------------------
# El color de cada estado sigue la convención clínica del odontograma:
# rojo = patología por tratar, azul = trabajo ya realizado.
ESTADOS_PIEZA = {
    "sano":     {"etiqueta": "Sano",     "color": "#FFFFFF", "texto": "#16232E"},
    "caries":   {"etiqueta": "Caries",   "color": "#D64545", "texto": "#FFFFFF"},
    "ausente":  {"etiqueta": "Ausente",  "color": "#8A97A0", "texto": "#FFFFFF"},
    "obturado": {"etiqueta": "Obturado", "color": "#1B6E8C", "texto": "#FFFFFF"},
    # Corona protésica: independiente del perno (ver CON_PERNO más abajo).
    "corona_buena": {"etiqueta": "Corona (buen estado)", "color": "#2E8B6E", "texto": "#FFFFFF"},
    "corona_mala":  {"etiqueta": "Corona (mal estado)",  "color": "#E08E3C", "texto": "#16232E"},
    # Solo queda la raíz — la corona está destruida o perdida. Distinto de
    # "ausente" (no queda nada de la pieza): aquí la raíz sigue en el hueso.
    "remanente_radicular": {"etiqueta": "Remanente radicular", "color": "#D64545", "texto": "#FFFFFF"},
}

# "sano" y "ausente"/"corona" pintan la pieza entera (van a la tabla odontograma).
# El resto se marca por CARA (va a odontograma_caras): una caries o una obturación
# en la cara oclusal no es lo mismo que en la mesial, y así se documenta en un
# odontograma real.
ESTADOS_CARA = {
    "sano":         ESTADOS_PIEZA["sano"],
    "caries":       ESTADOS_PIEZA["caries"],
    "obturado":     ESTADOS_PIEZA["obturado"],
    # Obturación deteriorada / filtrada / con caries secundaria: mismo trabajo
    # ya realizado que "obturado", pero necesita revisión — por eso el naranja,
    # a medio camino entre el rojo (patología) y el teal (trabajo sano).
    "obturado_mal": {"etiqueta": "Obturado (mal estado)", "color": "#E08E3C", "texto": "#16232E"},
}

# El perno (poste/muñón) es un booleano independiente del estado de la pieza:
# puede haber perno sin corona (a la espera de una) o corona sin perno.
PERNO_COLOR = "#16232E"

# Tipo de paciente: define qué dentición se dibuja en el odontograma.
# "nino" = dentición temporal/decidua (20 piezas, FDI 51-85, sin premolares).
# "adulto" = dentición permanente (32 piezas, FDI 11-48).
TIPOS_PACIENTE = {
    "adulto": "Adulto (dentición permanente — 32 piezas)",
    "nino":   "Niño (dentición temporal — 20 piezas)",
}

# Aparatos de ortodoncia. Azul (bueno) y rojo (malo) siguen la misma
# convención que el resto del odontograma clínico oficial (NTS 188-MINSA).
TIPOS_ORTODONCIA = {
    "fijo": "Fijo",
    "removible": "Removible",
}
ESTADOS_ORTODONCIA = {
    "bueno": {"etiqueta": "Buen estado", "color": "#1B6E8C"},
    "malo":  {"etiqueta": "Mal estado",  "color": "#D64545"},
}
ARCADAS = {
    "superior": "Superior",
    "inferior": "Inferior",
}

# Las 5 caras clínicas de una pieza dental.
CARAS_PIEZA = {
    "oclusal":    "Oclusal / incisal",
    "vestibular": "Vestibular",
    "lingual":    "Lingual / palatina",
    "mesial":     "Mesial",
    "distal":     "Distal",
}

# Tipo de mordida aproximado. Clasificación de Angle (clase_i/ii/iii) más las
# variantes clínicas que se anotan a simple vista sin necesidad de radiografía.
# Clase I es la mordida normal — no son dos categorías distintas.
TIPOS_MORDIDA = {
    "clase_i":       "Clase I (mordida normal)",
    "clase_ii":      "Clase II (mandíbula retraída)",
    "clase_iii":     "Clase III (mandíbula adelantada)",
    "cruzada":       "Mordida cruzada",
    "abierta":       "Mordida abierta",
    "borde_a_borde": "Borde a borde",
    "sobremordida":  "Sobremordida",
    "resalte":       "Resalte (overjet excesivo)",
}

# Extensiones aceptadas al subir imágenes al historial.
EXT_IMAGEN = {".jpg", ".jpeg", ".png", ".webp"}
