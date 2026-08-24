"""
Validación de documentos de identidad peruanos.

Cada tipo tiene su propia forma y no se pueden validar con la misma regla:
un DNI son 8 dígitos exactos y un carné de extranjería es alfanumérico y más
largo. Por eso el paciente guarda además el TIPO de documento.

Sobre el rigor de cada validación:

- RUC: se comprueba de verdad. Son 11 dígitos, empiezan por un prefijo
  válido y el último es un dígito verificador módulo 11 que se recalcula.
  Un RUC mal tipeado se detecta aquí, no en la SUNAT.
- DNI: se comprueba la forma (8 dígitos). El DNI lleva además un carácter
  verificador, pero va aparte del número y su algoritmo no es público, así
  que no se inventa una suma de control que rechazaría documentos buenos.
- Carné de extranjería y pasaporte: solo forma y longitud. Migraciones ha
  cambiado el formato con los años y no hay dígito verificador público.
"""

import re

TIPOS_DOCUMENTO = {
    "dni":       "DNI",
    "ce":        "Carné de extranjería",
    "pasaporte": "Pasaporte",
}

# Versión corta para la receta, donde el campo mide un tercio de la hoja.
ROTULO_CORTO = {
    "dni":       "DNI",
    "ce":        "C.E.",
    "pasaporte": "Pasap.",
}

# Prefijos que la SUNAT asigna según el tipo de contribuyente.
PREFIJOS_RUC = {
    "10": "Persona natural con negocio",
    "15": "Persona natural (no domiciliada)",
    "16": "Persona natural (no domiciliada)",
    "17": "Persona natural (no domiciliada)",
    "20": "Persona jurídica",
}

# Pesos del módulo 11 para los 10 primeros dígitos del RUC.
_PESOS_RUC = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def digito_verificador_ruc(diez_digitos: str) -> int:
    """El dígito 11 que le corresponde a los 10 primeros. Módulo 11."""
    suma = sum(int(d) * peso for d, peso in zip(diez_digitos, _PESOS_RUC))
    resto = 11 - (suma % 11)
    if resto == 10:
        return 0
    if resto == 11:
        return 1
    return resto


def validar_ruc(numero: str):
    """
    Devuelve (numero_limpio, None) si es válido, o (None, motivo) si no.
    Un RUC vacío se considera válido: el campo es opcional.
    """
    limpio = re.sub(r"[\s-]", "", (numero or ""))
    if not limpio:
        return None, None

    if not limpio.isdigit():
        return None, "El RUC solo puede tener números."
    if len(limpio) != 11:
        return None, f"El RUC debe tener 11 dígitos; este tiene {len(limpio)}."
    if limpio[:2] not in PREFIJOS_RUC:
        validos = ", ".join(sorted(PREFIJOS_RUC))
        return None, f"El RUC debe empezar con {validos}; este empieza con {limpio[:2]}."
    if int(limpio[10]) != digito_verificador_ruc(limpio[:10]):
        return None, "El RUC no pasa la verificación: revisa que no falte o sobre un dígito."

    return limpio, None


def validar_documento(tipo: str, numero: str):
    """
    Devuelve (numero_limpio, None) si es válido, o (None, motivo) si no.
    Un documento vacío se considera válido: el campo es opcional porque a
    veces se atiende primero y se piden los papeles después.
    """
    limpio = re.sub(r"[\s-]", "", (numero or "")).upper()
    if not limpio:
        return None, None

    etiqueta = TIPOS_DOCUMENTO.get(tipo, "documento")

    if tipo == "dni":
        if not limpio.isdigit():
            return None, "El DNI solo puede tener números."
        if len(limpio) != 8:
            return None, f"El DNI debe tener 8 dígitos; este tiene {len(limpio)}."

    elif tipo == "ce":
        if not limpio.isalnum():
            return None, f"El {etiqueta.lower()} solo puede tener letras y números."
        if not 9 <= len(limpio) <= 12:
            return None, (f"El {etiqueta.lower()} debe tener entre 9 y 12 caracteres; "
                          f"este tiene {len(limpio)}.")

    elif tipo == "pasaporte":
        if not limpio.isalnum():
            return None, "El pasaporte solo puede tener letras y números."
        if not 6 <= len(limpio) <= 12:
            return None, f"El pasaporte debe tener entre 6 y 12 caracteres; este tiene {len(limpio)}."

    else:
        return None, "Tipo de documento no reconocido."

    return limpio, None
