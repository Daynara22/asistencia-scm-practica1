"""
validaciones.py - Validación y limpieza de los datos que ingresa el usuario.

Cada función recibe el texto tal como llega del formulario y devuelve el
valor limpio, o lanza ErrorValidacion con un mensaje para mostrar en
pantalla.
"""
import re
from datetime import datetime

# Letras (con tildes y ñ), y palabras separadas por espacio, guion o
# apóstrofo.
PATRON_NOMBRE = re.compile(r"[^\W\d_]+(?:[ '\-][^\W\d_]+)*")

# Un email simple: algo@dominio.ext (sin espacios).
PATRON_EMAIL = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")

LARGO_MAXIMO_NOMBRE = 50
CLAVE_MINIMO = 8
CLAVE_MAXIMO = 128


class ErrorValidacion(Exception):
    """Error con un mensaje pensado para mostrarle al usuario."""


def validar_dni(texto):
    """Devuelve el DNI limpio (solo dígitos) o lanza ErrorValidacion."""
    # Se aceptan puntos y espacios (ej. 45.123.456) y se quitan.
    dni = str(texto or "").strip().replace(".", "").replace(" ", "")
    if not dni:
        raise ErrorValidacion("Ingresá un DNI.")
    if not re.fullmatch(r"[0-9]+", dni):
        raise ErrorValidacion("El DNI solo puede tener números.")
    if len(dni) not in (7, 8):
        raise ErrorValidacion("El DNI debe tener 7 u 8 dígitos.")
    return dni


def validar_nombre(texto, campo):
    """
    Valida un nombre o apellido y lo devuelve prolijo.

    Ejemplo: 'maría  josé' -> 'María José'.
    """
    limpio = " ".join(str(texto or "").split())
    if not limpio:
        raise ErrorValidacion(f"El {campo} no puede estar vacío.")
    if len(limpio) > LARGO_MAXIMO_NOMBRE:
        raise ErrorValidacion(
            f"El {campo} no puede tener más de {LARGO_MAXIMO_NOMBRE} "
            "caracteres.")
    if not PATRON_NOMBRE.fullmatch(limpio):
        raise ErrorValidacion(
            f"El {campo} solo puede tener letras, espacios, guiones o "
            "apóstrofos.")
    return limpio.title()


def validar_email(texto):
    """Devuelve el email limpio y en minúsculas, o lanza ErrorValidacion."""
    email = str(texto or "").strip().lower()
    if not email:
        raise ErrorValidacion("Ingresá un email.")
    if len(email) > 254 or not PATRON_EMAIL.fullmatch(email):
        raise ErrorValidacion(
            "El email no es válido (por ejemplo: nombre@escuela.edu.ar).")
    return email


def validar_clave(clave, repetida):
    """
    Revisa que la contraseña nueva sea segura.

    Mínimo 8 caracteres, con al menos una letra, un número y un carácter
    especial, y que coincida con la repetición.
    """
    clave = str(clave or "")
    if not clave:
        raise ErrorValidacion("Ingresá una contraseña.")
    if len(clave) < CLAVE_MINIMO:
        raise ErrorValidacion(
            f"La contraseña debe tener al menos {CLAVE_MINIMO} caracteres.")
    if len(clave) > CLAVE_MAXIMO:
        raise ErrorValidacion(
            f"La contraseña no puede tener más de {CLAVE_MAXIMO} "
            "caracteres.")
    if any(c.isspace() for c in clave):
        raise ErrorValidacion("La contraseña no puede tener espacios.")
    if not any(c.isalpha() for c in clave):
        raise ErrorValidacion("La contraseña debe tener al menos una letra.")
    if not any(c.isdigit() for c in clave):
        raise ErrorValidacion("La contraseña debe tener al menos un número.")
    if all(c.isalnum() for c in clave):
        raise ErrorValidacion(
            "La contraseña debe tener al menos un carácter especial "
            "(por ejemplo: ! @ # $ % & * ?).")
    if clave != str(repetida or ""):
        raise ErrorValidacion("Las dos contraseñas no coinciden.")
    return clave


def validar_fecha(texto):
    """Convierte 'AAAA-MM-DD' en un objeto date. Revisa que la fecha
    exista."""
    texto = str(texto or "").strip()
    if not texto:
        raise ErrorValidacion("Ingresá una fecha.")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", texto):
        raise ErrorValidacion(
            "La fecha debe tener el formato AAAA-MM-DD "
            "(por ejemplo 2026-11-06).")
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        raise ErrorValidacion(f"La fecha {texto} no existe.")


def validar_hora(texto):
    """
    Convierte 'HH:MM' en un objeto time.

    Así las horas se comparan como horas y no como texto.
    """
    texto = str(texto or "").strip()
    if not texto:
        raise ErrorValidacion("Ingresá una hora.")
    if not re.fullmatch(r"[0-9]{2}:[0-9]{2}", texto):
        raise ErrorValidacion(
            "La hora debe tener el formato HH:MM (por ejemplo 08:15).")
    try:
        return datetime.strptime(texto, "%H:%M").time()
    except ValueError:
        raise ErrorValidacion(f"La hora {texto} no es válida.")
