"""Valores fijos del dominio. Mantener sincronizados con los CHECK de schema.sql."""

# --- Datos de la clínica (para el encabezado del PDF de receta) -----------
CLINICA = {
    "nombre": "KrizDent",
    "eslogan": "Sonrisas sanas y brillantes",
    "celular": "900181998",
    "direccion": "Santa Cruz de Cajamarquilla, MZ D lote 5",
}

# --- Almacén -----------------------------------------------------------------
# Agrupación clínica de insumos de salud (no genérica tipo "categoría 1, 2, 3":
# así el listado del almacén se puede filtrar por lo que realmente se busca).
CATEGORIAS_ALMACEN = {
    "material_curacion":     "Material de curación",
    "proteccion_personal":   "Protección personal",
    "anestesia_desechables": "Anestesia y desechables",
    "insumos_dentales":      "Insumos dentales",
    "medicamentos":          "Medicamentos",
    "instrumental":          "Instrumental",
    "otros":                 "Otros",
}

UNIDADES_MEDIDA = {
    "unidad":  "Unidad",
    "paquete": "Paquete",
    "caja":    "Caja",
    "frasco":  "Frasco",
    "ml":      "Mililitros (ml)",
    "mg":      "Miligramos (mg)",
    "gr":      "Gramos (gr)",
}

TIPOS_MOVIMIENTO = {
    "entrada": {"etiqueta": "Entrada", "clase": "estado-completada"},
    "salida":  {"etiqueta": "Salida",  "clase": "estado-cancelada"},
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
# "corto" es el rótulo para la paleta del odontograma, donde el espacio manda;
# "etiqueta" es el nombre completo que va en tablas, informes y PDF.
ESTADOS_PIEZA = {
    "sano":     {"etiqueta": "Sano",     "corto": "Sano",     "color": "#FFFFFF", "texto": "#16232E"},
    "caries":   {"etiqueta": "Caries",   "corto": "Caries",   "color": "#D64545", "texto": "#FFFFFF"},
    "ausente":  {"etiqueta": "Ausente",  "corto": "Ausente",  "color": "#8A97A0", "texto": "#FFFFFF"},
    "obturado": {"etiqueta": "Obturado", "corto": "Obturado", "color": "#1B6E8C", "texto": "#FFFFFF"},
    # Corona protésica: independiente del perno (ver CON_PERNO más abajo).
    "corona_buena": {"etiqueta": "Corona (buen estado)", "corto": "Corona buena", "color": "#2E8B6E", "texto": "#FFFFFF"},
    "corona_mala":  {"etiqueta": "Corona (mal estado)",  "corto": "Corona mala",  "color": "#E08E3C", "texto": "#16232E"},
    # Solo queda la raíz — la corona está destruida o perdida. Distinto de
    # "ausente" (no queda nada de la pieza): aquí la raíz sigue en el hueso.
    "remanente_radicular": {"etiqueta": "Remanente radicular", "corto": "Remanente", "color": "#D64545", "texto": "#FFFFFF"},
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
    "obturado_mal": {"etiqueta": "Obturado (mal estado)", "corto": "Obturado malo", "color": "#E08E3C", "texto": "#16232E"},
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

# --- Presupuestos y pagos ---------------------------------------------------
ESTADOS_TRATAMIENTO = {
    "pendiente":   {"etiqueta": "Pendiente",   "clase": "estado-pendiente"},
    "en_proceso":  {"etiqueta": "En proceso",  "clase": "estado-pendiente"},
    "completado":  {"etiqueta": "Completado",  "clase": "estado-completada"},
    "cancelado":   {"etiqueta": "Cancelado",   "clase": "estado-cancelada"},
}
METODOS_PAGO = {
    "efectivo":      "Efectivo",
    "yape_plin":     "Yape / Plin",
    "tarjeta":       "Tarjeta",
    "transferencia": "Transferencia",
    "otro":          "Otro",
}

# --- Consentimiento informado -----------------------------------------------
# Texto base editable al momento de firmar. Cumple con mencionar el
# almacenamiento digital de datos, como recomienda el propio README (Ley 29733).
# Lleva {clinica} porque cada clínica que alquila el sistema firma con su
# propio nombre: ver texto_consentimiento() en routes/consentimientos.py.
CONSENTIMIENTO_TEXTO_BASE = (
    "Declaro que he sido informado(a) de forma clara sobre el diagnóstico, "
    "el tratamiento odontológico propuesto, sus alternativas, riesgos y "
    "beneficios, y que todas mis dudas fueron resueltas antes de firmar. "
    "Autorizo a {clinica} a realizar el tratamiento descrito y entiendo que "
    "mi historial clínico se almacena digitalmente en un servicio en la nube."
)

# --- Laboratorio dental ------------------------------------------------------
ESTADOS_LABORATORIO = {
    "enviado":    {"etiqueta": "Enviado",    "clase": "estado-pendiente"},
    "en_proceso": {"etiqueta": "En proceso", "clase": "estado-pendiente"},
    "listo":      {"etiqueta": "Listo para recoger", "clase": "estado-completada"},
    "entregado":  {"etiqueta": "Entregado",  "clase": "estado-completada"},
}

# --- Cuentas, planes y permisos ---------------------------------------------
# Los módulos que se pueden contratar/activar. Coinciden con el menú lateral:
# lo que no está en el plan de la clínica no aparece y su URL queda bloqueada.
MODULOS = {
    "panel":         "Panel",
    "pacientes":     "Pacientes",
    "agenda":        "Agenda",
    "presupuestos":  "Presupuestos",
    "recetas":       "Recetas",
    "almacen":       "Almacén",
    "reportes":      "Reportes",
    "profesionales": "Profesionales",
}

# Qué módulo gobierna cada blueprint. Los blueprints que viven dentro de la
# ficha del paciente (odontograma, periodontograma, laboratorio...) dependen
# del módulo "pacientes": no se contratan por separado.
MODULO_DE_BLUEPRINT = {
    "dashboard":       "panel",
    "pacientes":       "pacientes",
    "historial":       "pacientes",
    "odontograma":     "pacientes",
    "periodontograma": "pacientes",
    "consentimientos": "pacientes",
    "laboratorio":     "pacientes",
    "citas":           "agenda",
    "finanzas":        "presupuestos",
    "recetas":         "recetas",
    "almacen":         "almacen",
    "reportes":        "reportes",
    "profesionales":   "profesionales",
}

# superadmin = dueño de la plataforma (no pertenece a ninguna clínica y nunca
# ve historias clínicas). dueno = titular de la clínica, administra a los suyos.
ROLES = {
    "superadmin": "Superadministrador",
    "dueno":      "Titular de la clínica",
    "usuario":    "Usuario",
}
