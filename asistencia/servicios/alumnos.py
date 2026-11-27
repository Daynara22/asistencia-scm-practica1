"""alumnos.py - Alta, búsqueda y listado de alumnos."""
import sqlite3
import unicodedata

from asistencia.bd import transaccion
from asistencia.modelos import Alumno
from asistencia.validaciones import (ErrorValidacion, validar_dni,
                                     validar_nombre)


def _por_dni(conexion, dni):
    """Busca un alumno por DNI ya validado. Devuelve None si no existe."""
    fila = conexion.execute(
        "SELECT * FROM alumnos WHERE dni = ?", (dni,)).fetchone()
    return Alumno.desde_fila(fila) if fila else None


def clave_de_orden(texto):
    """
    Texto para ordenar alfabéticamente sin que las tildes molesten.

    'Álvarez' -> 'alvarez' (si no, la Á quedaría después de la Z).
    """
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes
                   if not unicodedata.combining(c)).casefold()


def alta(conexion, dni, nombre, apellido):
    """Da de alta un alumno nuevo y lo devuelve. El DNI no puede
    repetirse."""
    dni = validar_dni(dni)
    nombre = validar_nombre(nombre, "nombre")
    apellido = validar_nombre(apellido, "apellido")

    try:
        with transaccion(conexion):
            existente = _por_dni(conexion, dni)
            if existente:
                raise ErrorValidacion(
                    f"Ya existe un alumno con el DNI {dni} "
                    f"({existente.nombre_completo}).")
            cursor = conexion.execute(
                "INSERT INTO alumnos (dni, nombre, apellido) "
                "VALUES (?, ?, ?)", (dni, nombre, apellido))
    except sqlite3.IntegrityError:
        # Respaldo de la restricción UNIQUE de la base.
        raise ErrorValidacion(f"Ya existe un alumno con el DNI {dni}.")
    return Alumno(cursor.lastrowid, dni, nombre, apellido)


def buscar_por_dni(conexion, dni):
    """Devuelve el alumno con ese DNI o lanza ErrorValidacion si no
    existe."""
    dni = validar_dni(dni)
    alumno = _por_dni(conexion, dni)
    if alumno is None:
        raise ErrorValidacion(
            f"No hay ningún alumno registrado con el DNI {dni}.")
    return alumno


def listar(conexion):
    """Lista de alumnos ordenada por apellido y nombre."""
    alumnos = [Alumno.desde_fila(fila) for fila in
               conexion.execute("SELECT * FROM alumnos")]
    # Se ordena en Python porque SQLite no ordena bien las tildes.
    alumnos.sort(key=lambda a: (clave_de_orden(a.apellido),
                                clave_de_orden(a.nombre)))
    return alumnos


def cantidad(conexion):
    """Cantidad total de alumnos registrados."""
    return conexion.execute("SELECT COUNT(*) FROM alumnos").fetchone()[0]
