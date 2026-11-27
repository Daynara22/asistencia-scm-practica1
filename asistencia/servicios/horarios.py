"""
horarios.py - ABM (alta, baja y modificación) de horarios de clase.

Un horario es un bloque de un curso: día de la semana, hora de inicio,
hora de fin y materia. Dos bloques del mismo curso y el mismo día no
pueden superponerse (sí pueden tocarse: uno termina 10:00 y el otro
empieza 10:00).
"""
from asistencia.bd import transaccion
from asistencia.modelos import DIAS, Horario
from asistencia.servicios import cursos, materias
from asistencia.validaciones import (ErrorValidacion, validar_entero,
                                     validar_hora, validar_id,
                                     validar_texto)


def _validar(conexion, curso_id, dia, hora_inicio, hora_fin, materia):
    """Valida los campos y los devuelve limpios."""
    if not str(curso_id or "").strip():
        raise ErrorValidacion("Elegí el curso.")
    curso = cursos.buscar(conexion, curso_id)
    dia = validar_entero(dia, "el día", 0, len(DIAS) - 1)
    inicio = validar_hora(hora_inicio)
    fin = validar_hora(hora_fin)
    if inicio >= fin:
        raise ErrorValidacion(
            "La hora de fin tiene que ser posterior a la de inicio.")
    materia = validar_texto(materia, "materia")
    return (curso, dia, inicio.strftime("%H:%M"), fin.strftime("%H:%M"),
            materia)


def _revisar_superposicion(conexion, curso, dia, inicio, fin,
                           propio_id=None):
    """
    Lanza ErrorValidacion si el bloque se pisa con otro del mismo curso.

    Dos bloques se superponen si cada uno empieza antes de que termine
    el otro. Las horas 'HH:MM' se pueden comparar como texto porque
    siempre tienen dos dígitos.
    """
    fila = conexion.execute(
        "SELECT h.hora_inicio, h.hora_fin, m.nombre AS materia "
        "FROM horarios h JOIN materias m ON m.id = h.materia_id "
        "WHERE h.curso_id = ? AND h.dia = ? AND h.id IS NOT ? "
        "AND h.hora_inicio < ? AND ? < h.hora_fin",
        (curso.id, dia, propio_id, fin, inicio)).fetchone()
    if fila:
        raise ErrorValidacion(
            f"Se superpone con {fila['materia']} del {DIAS[dia].lower()} "
            f"de {fila['hora_inicio']} a {fila['hora_fin']} en "
            f"{curso.nombre_completo}.")


def alta(conexion, curso_id, dia, hora_inicio, hora_fin, materia):
    """Da de alta un bloque de horario y lo devuelve."""
    curso, dia, inicio, fin, materia = _validar(
        conexion, curso_id, dia, hora_inicio, hora_fin, materia)
    with transaccion(conexion):
        _revisar_superposicion(conexion, curso, dia, inicio, fin)
        materia_id = materias.obtener_o_crear(conexion, materia)
        horario_id = conexion.execute(
            "INSERT INTO horarios "
            "(curso_id, dia, hora_inicio, hora_fin, materia_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (curso.id, dia, inicio, fin, materia_id)).lastrowid
    return Horario(horario_id, curso.id, dia, inicio, fin, materia_id)


def modificar(conexion, horario_id, curso_id, dia, hora_inicio, hora_fin,
              materia):
    """Cambia un bloque de horario y lo devuelve actualizado."""
    horario = buscar(conexion, horario_id)
    curso, dia, inicio, fin, materia = _validar(
        conexion, curso_id, dia, hora_inicio, hora_fin, materia)
    with transaccion(conexion):
        _revisar_superposicion(conexion, curso, dia, inicio, fin,
                               horario.id)
        materia_id = materias.obtener_o_crear(conexion, materia)
        conexion.execute(
            "UPDATE horarios SET curso_id = ?, dia = ?, hora_inicio = ?, "
            "hora_fin = ?, materia_id = ? WHERE id = ?",
            (curso.id, dia, inicio, fin, materia_id, horario.id))
    return Horario(horario.id, curso.id, dia, inicio, fin, materia_id)


def eliminar(conexion, horario_id):
    """Da de baja un bloque de horario y lo devuelve."""
    horario = buscar(conexion, horario_id)
    with transaccion(conexion):
        conexion.execute("DELETE FROM horarios WHERE id = ?",
                         (horario.id,))
    return horario


def obtener(conexion, horario_id):
    """Devuelve el horario con ese id, o None si no existe."""
    fila = conexion.execute("SELECT * FROM horarios WHERE id = ?",
                            (horario_id,)).fetchone()
    return Horario.desde_fila(fila) if fila else None


def buscar(conexion, horario_id):
    """Como obtener, pero lanza ErrorValidacion si no existe."""
    horario = obtener(conexion, validar_id(horario_id, "El horario"))
    if horario is None:
        raise ErrorValidacion("El horario indicado no existe.")
    return horario


def listar(conexion, curso_id=None):
    """
    Bloques de horario ordenados por curso, día y hora de inicio.

    Si se indica curso_id, solo los de ese curso. Cada elemento es un
    diccionario con los datos del bloque, el día escrito, la materia y el
    nombre del curso.
    """
    filas = conexion.execute(
        "SELECT h.*, m.nombre AS materia, c.nombre AS curso_nombre, "
        "c.anio, c.division "
        "FROM horarios h JOIN materias m ON m.id = h.materia_id "
        "JOIN cursos c ON c.id = h.curso_id "
        "WHERE ? IS NULL OR h.curso_id = ? "
        "ORDER BY c.anio, c.division, c.nombre, h.dia, h.hora_inicio",
        (curso_id, curso_id)).fetchall()
    return [{**dict(fila), "nombre_dia": DIAS[fila["dia"]],
             "curso": (f"{fila['curso_nombre']} {fila['anio']}° "
                       f"{fila['division']}")}
            for fila in filas]
