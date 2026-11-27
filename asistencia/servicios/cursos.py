"""
cursos.py - ABM (alta, baja y modificación) de cursos.

Un curso tiene nombre, año (1 a 7), división, un docente a cargo y,
opcionalmente, su propio límite de faltas (si no tiene, usa el general).
No puede haber dos cursos con el mismo nombre, año y división.
"""
from asistencia.bd import transaccion
from asistencia.modelos import Curso
from asistencia.servicios import docentes
from asistencia.validaciones import (ErrorValidacion, validar_division,
                                     validar_entero, validar_id,
                                     validar_texto)

ANIO_MINIMO = 1
ANIO_MAXIMO = 7
LIMITE_MAXIMO = 365


def _validar_limite(texto):
    """Límite de faltas propio del curso; vacío = usa el general
    (None)."""
    if not str(texto or "").strip():
        return None
    return validar_entero(texto, "el límite de faltas", 1, LIMITE_MAXIMO)


def _validar(conexion, nombre, anio, division, docente_id):
    """Valida los campos y devuelve (nombre, anio, division, docente)."""
    nombre = validar_texto(nombre, "nombre del curso")
    anio = validar_entero(anio, "el año", ANIO_MINIMO, ANIO_MAXIMO)
    division = validar_division(division)
    if not str(docente_id or "").strip():
        raise ErrorValidacion("Elegí el docente a cargo del curso.")
    docente = docentes.buscar(conexion, docente_id)
    return nombre, anio, division, docente


def _revisar_repetido(conexion, nombre, anio, division, propio_id=None):
    """Lanza ErrorValidacion si ya existe un curso igual."""
    fila = conexion.execute(
        "SELECT 1 FROM cursos WHERE nombre = ? AND anio = ? "
        "AND division = ? AND id IS NOT ?",
        (nombre, anio, division, propio_id)).fetchone()
    if fila:
        raise ErrorValidacion(
            f"Ya existe el curso {nombre} {anio}° {division}.")


def alta(conexion, nombre, anio, division, docente_id, limite_faltas=""):
    """Da de alta un curso y lo devuelve."""
    nombre, anio, division, docente = _validar(conexion, nombre, anio,
                                               division, docente_id)
    limite = _validar_limite(limite_faltas)
    with transaccion(conexion):
        _revisar_repetido(conexion, nombre, anio, division)
        curso_id = conexion.execute(
            "INSERT INTO cursos (nombre, anio, division, docente_id, "
            "limite_faltas) VALUES (?, ?, ?, ?, ?)",
            (nombre, anio, division, docente.id, limite)).lastrowid
    return Curso(curso_id, nombre, anio, division, docente.id, limite)


def modificar(conexion, curso_id, nombre, anio, division, docente_id,
              limite_faltas=""):
    """Cambia los datos de un curso y lo devuelve actualizado."""
    curso = buscar(conexion, curso_id)
    nombre, anio, division, docente = _validar(conexion, nombre, anio,
                                               division, docente_id)
    limite = _validar_limite(limite_faltas)
    with transaccion(conexion):
        _revisar_repetido(conexion, nombre, anio, division, curso.id)
        conexion.execute(
            "UPDATE cursos SET nombre = ?, anio = ?, division = ?, "
            "docente_id = ?, limite_faltas = ? WHERE id = ?",
            (nombre, anio, division, docente.id, limite, curso.id))
    return Curso(curso.id, nombre, anio, division, docente.id, limite)


def eliminar(conexion, curso_id):
    """
    Da de baja un curso (y sus horarios) y lo devuelve.

    No se puede si tiene alumnos: primero hay que pasarlos a otro curso.
    """
    curso = buscar(conexion, curso_id)
    with transaccion(conexion):
        cantidad = conexion.execute(
            "SELECT COUNT(*) FROM alumnos WHERE curso_id = ?",
            (curso.id,)).fetchone()[0]
        if cantidad:
            raise ErrorValidacion(
                f"El curso {curso.nombre_completo} tiene {cantidad} "
                f"alumno{'' if cantidad == 1 else 's'}. Pasalos a otro "
                "curso antes de darlo de baja.")
        # Los horarios del curso se borran solos (ON DELETE CASCADE).
        conexion.execute("DELETE FROM cursos WHERE id = ?", (curso.id,))
    return curso


def obtener(conexion, curso_id):
    """Devuelve el curso con ese id, o None si no existe."""
    fila = conexion.execute("SELECT * FROM cursos WHERE id = ?",
                            (curso_id,)).fetchone()
    return Curso.desde_fila(fila) if fila else None


def buscar(conexion, curso_id):
    """Como obtener, pero lanza ErrorValidacion si no existe."""
    curso = obtener(conexion, validar_id(curso_id, "El curso"))
    if curso is None:
        raise ErrorValidacion("El curso indicado no existe.")
    return curso


def listar(conexion):
    """
    Todos los cursos ordenados por año, división y nombre.

    Cada elemento es un diccionario con los datos del curso, el nombre
    completo, el docente a cargo y la cantidad de alumnos y horarios.
    """
    filas = conexion.execute(
        "SELECT c.*, d.nombre || ' ' || d.apellido AS docente, "
        "(SELECT COUNT(*) FROM alumnos a WHERE a.curso_id = c.id) "
        "AS alumnos, "
        "(SELECT COUNT(*) FROM horarios h WHERE h.curso_id = c.id) "
        "AS horarios "
        "FROM cursos c JOIN docentes d ON d.id = c.docente_id "
        "ORDER BY c.anio, c.division, c.nombre").fetchall()
    return [{**dict(fila), "nombre_completo": Curso.desde_fila(
        fila).nombre_completo} for fila in filas]
