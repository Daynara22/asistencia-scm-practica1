"""
alumnos.py - ABM (alta, baja y modificación) de alumnos.

Un alumno tiene DNI (único), nombre, apellido, email (único) y curso.
Al dar de alta un alumno nuevo, el email y el curso son obligatorios. Al
modificarlo son opcionales, porque los alumnos cargados antes de la
versión 3 no los tienen.
"""
import sqlite3
import unicodedata

from asistencia.bd import transaccion
from asistencia.modelos import Alumno
from asistencia.servicios import cursos
from asistencia.validaciones import (ErrorValidacion, validar_dni,
                                     validar_email, validar_id,
                                     validar_nombre)


def clave_de_orden(texto):
    """
    Texto para ordenar alfabéticamente sin que las tildes molesten.

    'Álvarez' -> 'alvarez' (si no, la Á quedaría después de la Z).
    """
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin_tildes
                   if not unicodedata.combining(c)).casefold()


def _por_dni(conexion, dni):
    """Busca un alumno por DNI ya validado. Devuelve None si no existe."""
    fila = conexion.execute(
        "SELECT * FROM alumnos WHERE dni = ?", (dni,)).fetchone()
    return Alumno.desde_fila(fila) if fila else None


def _validar(conexion, dni, nombre, apellido, email, curso_id,
             obligatorios):
    """
    Valida los campos y los devuelve limpios.

    Con obligatorios=False, el email y el curso pueden quedar vacíos
    (se guardan como None).
    """
    dni = validar_dni(dni)
    nombre = validar_nombre(nombre, "nombre")
    apellido = validar_nombre(apellido, "apellido")

    email = str(email or "").strip()
    if email or obligatorios:
        email = validar_email(email)
    else:
        email = None

    if str(curso_id or "").strip():
        curso_id = cursos.buscar(conexion, curso_id).id
    elif obligatorios:
        raise ErrorValidacion("Elegí el curso del alumno.")
    else:
        curso_id = None
    return dni, nombre, apellido, email, curso_id


def _revisar_repetidos(conexion, dni, email, propio_id=None):
    """Lanza ErrorValidacion si otro alumno ya usa ese DNI o email."""
    existente = _por_dni(conexion, dni)
    if existente and existente.id != propio_id:
        raise ErrorValidacion(
            f"Ya existe un alumno con el DNI {dni} "
            f"({existente.nombre_completo}).")
    if email:
        fila = conexion.execute(
            "SELECT nombre, apellido FROM alumnos WHERE email = ? "
            "AND id IS NOT ?", (email, propio_id)).fetchone()
        if fila:
            raise ErrorValidacion(
                f"Ya existe un alumno con el email {email} "
                f"({fila['nombre']} {fila['apellido']}).")


def alta(conexion, dni, nombre, apellido, email, curso_id):
    """Da de alta un alumno nuevo y lo devuelve."""
    dni, nombre, apellido, email, curso_id = _validar(
        conexion, dni, nombre, apellido, email, curso_id, obligatorios=True)
    try:
        with transaccion(conexion):
            _revisar_repetidos(conexion, dni, email)
            cursor = conexion.execute(
                "INSERT INTO alumnos (dni, nombre, apellido, email, "
                "curso_id) VALUES (?, ?, ?, ?, ?)",
                (dni, nombre, apellido, email, curso_id))
    except sqlite3.IntegrityError:
        # Respaldo de las restricciones UNIQUE de la base.
        raise ErrorValidacion(
            f"Ya existe un alumno con el DNI {dni} o el email {email}.")
    return Alumno(cursor.lastrowid, dni, nombre, apellido, email, curso_id)


def modificar(conexion, alumno_id, dni, nombre, apellido, email, curso_id):
    """
    Cambia los datos de un alumno y lo devuelve actualizado.

    Si el alumno tiene cuenta de usuario, también se actualiza el nombre
    de la cuenta.
    """
    alumno = buscar(conexion, alumno_id)
    dni, nombre, apellido, email, curso_id = _validar(
        conexion, dni, nombre, apellido, email, curso_id,
        obligatorios=False)
    try:
        with transaccion(conexion):
            _revisar_repetidos(conexion, dni, email, alumno.id)
            conexion.execute(
                "UPDATE alumnos SET dni = ?, nombre = ?, apellido = ?, "
                "email = ?, curso_id = ? WHERE id = ?",
                (dni, nombre, apellido, email, curso_id, alumno.id))
            conexion.execute(
                "UPDATE usuarios SET nombre = ?, apellido = ? "
                "WHERE alumno_id = ?", (nombre, apellido, alumno.id))
    except sqlite3.IntegrityError:
        raise ErrorValidacion(
            f"Ya existe un alumno con el DNI {dni} o el email {email}.")
    return Alumno(alumno.id, dni, nombre, apellido, email, curso_id)


def eliminar(conexion, alumno_id):
    """
    Da de baja un alumno y lo devuelve.

    Se borran también sus registros de asistencia y su cuenta de usuario
    (si tenía), todo en una misma transacción.
    """
    alumno = buscar(conexion, alumno_id)
    with transaccion(conexion):
        conexion.execute("DELETE FROM asistencias WHERE alumno_id = ?",
                         (alumno.id,))
        conexion.execute("DELETE FROM usuarios WHERE alumno_id = ?",
                         (alumno.id,))
        conexion.execute("DELETE FROM alumnos WHERE id = ?", (alumno.id,))
    return alumno


def buscar_por_dni(conexion, dni):
    """Devuelve el alumno con ese DNI o lanza ErrorValidacion si no
    existe."""
    dni = validar_dni(dni)
    alumno = _por_dni(conexion, dni)
    if alumno is None:
        raise ErrorValidacion(
            f"No hay ningún alumno registrado con el DNI {dni}.")
    return alumno


def obtener(conexion, alumno_id):
    """Devuelve el alumno con ese id, o None si no existe."""
    fila = conexion.execute(
        "SELECT * FROM alumnos WHERE id = ?", (alumno_id,)).fetchone()
    return Alumno.desde_fila(fila) if fila else None


def buscar(conexion, alumno_id):
    """Como obtener, pero lanza ErrorValidacion si no existe."""
    alumno = obtener(conexion, validar_id(alumno_id, "El alumno"))
    if alumno is None:
        raise ErrorValidacion("El alumno indicado no existe.")
    return alumno


def listar(conexion, curso_id=None):
    """
    Lista de alumnos ordenada por apellido y nombre.

    Si se indica curso_id, solo los de ese curso.
    """
    alumnos = [Alumno.desde_fila(fila) for fila in conexion.execute(
        "SELECT * FROM alumnos WHERE ? IS NULL OR curso_id = ?",
        (curso_id, curso_id))]
    # Se ordena en Python porque SQLite no ordena bien las tildes.
    alumnos.sort(key=lambda a: (clave_de_orden(a.apellido),
                                clave_de_orden(a.nombre)))
    return alumnos


def cantidad(conexion):
    """Cantidad total de alumnos registrados."""
    return conexion.execute("SELECT COUNT(*) FROM alumnos").fetchone()[0]
