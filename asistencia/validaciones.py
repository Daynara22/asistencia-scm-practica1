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

# Nombres de materias y cursos: letras, números y algunos signos
# (por ejemplo "Programación III" o "Matemática 2").
PATRON_TEXTO = re.compile(r"[^\W_]+(?:(?:[ '\-]|\. ?)[^\W_]+)*\.?")

LARGO_MAXIMO_NOMBRE = 50
LARGO_MAXIMO_TEXTO = 60
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


def validar_texto(texto, campo, largo_maximo=LARGO_MAXIMO_TEXTO):
    """
    Valida un nombre de materia o de curso y lo devuelve prolijo.

    Admite letras, números, espacios, puntos, guiones y apóstrofos.
    Solo se pone en mayúscula la primera letra ('programación III' ->
    'Programación III').
    """
    limpio = " ".join(str(texto or "").split())
    if not limpio:
        raise ErrorValidacion(f"El campo {campo} no puede estar vacío.")
    if len(limpio) > largo_maximo:
        raise ErrorValidacion(
            f"El campo {campo} no puede tener más de {largo_maximo} "
            "caracteres.")
    if not PATRON_TEXTO.fullmatch(limpio):
        raise ErrorValidacion(
            f"El campo {campo} solo puede tener letras, números, espacios, "
            "puntos o guiones.")
    return limpio[0].upper() + limpio[1:]


def validar_entero(texto, campo, minimo, maximo):
    """Convierte el texto en un número entero entre minimo y maximo."""
    texto = str(texto if texto is not None else "").strip()
    if not texto:
        raise ErrorValidacion(f"Ingresá {campo}.")
    if not re.fullmatch(r"-?[0-9]+", texto):
        raise ErrorValidacion(f"El campo {campo} debe ser un número.")
    numero = int(texto)
    if not minimo <= numero <= maximo:
        raise ErrorValidacion(
            f"El campo {campo} debe estar entre {minimo} y {maximo}.")
    return numero


def validar_division(texto):
    """La división del curso: 1 a 3 letras o números ('A', '2', '1B')."""
    division = str(texto or "").strip().upper()
    if not division:
        raise ErrorValidacion("Ingresá la división.")
    if not re.fullmatch(r"[A-Z0-9]{1,3}", division):
        raise ErrorValidacion(
            "La división debe tener de 1 a 3 letras o números "
            "(por ejemplo A o 2).")
    return division


def validar_materias(texto):
    """
    Convierte 'Matemática, Física' en ['Matemática', 'Física'].

    Pide al menos una materia y quita las repetidas.
    """
    materias = []
    for parte in str(texto or "").split(","):
        if parte.strip():
            materia = validar_texto(parte, "materia")
            if materia.casefold() not in (m.casefold() for m in materias):
                materias.append(materia)
    if not materias:
        raise ErrorValidacion(
            "Ingresá al menos una materia (separadas por comas).")
    return materias


def validar_id(texto, que):
    """
    Convierte el id que llega de un formulario o de la dirección en int.

    'que' describe lo buscado ('El curso', 'El docente'...) para el
    mensaje de error.
    """
    try:
        numero = int(str(texto).strip())
    except (TypeError, ValueError):
        raise ErrorValidacion(f"{que} indicado no existe.")
    if numero <= 0:
        raise ErrorValidacion(f"{que} indicado no existe.")
    return numero
