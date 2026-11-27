"""
docentes.py - ABM (alta, baja y modificación) de docentes.

Un docente tiene DNI y email únicos y dicta una o más materias. No es lo
mismo que una cuenta de usuario: si existe una cuenta con el mismo email,
se muestra como vinculada.
"""
from asistencia.bd import transaccion
from asistencia.modelos import Docente
from asistencia.servicios import materias
from asistencia.validaciones import (ErrorValidacion, validar_dni,
                                     validar_email, validar_id,
                                     validar_materias, validar_nombre)


def _materias_de(conexion, docente_id):
    """Nombres de las materias del docente, en orden alfabético."""
    return [fila["nombre"] for fila in conexion.execute(
        "SELECT m.nombre FROM docente_materias dm "
        "JOIN materias m ON m.id = dm.materia_id "
        "WHERE dm.docente_id = ? ORDER BY m.nombre", (docente_id,))]


def _validar(dni, nombre, apellido, email, materias_texto):
    """Valida todos los campos y los devuelve limpios."""
    return (validar_dni(dni), validar_nombre(nombre, "nombre"),
            validar_nombre(apellido, "apellido"), validar_email(email),
            validar_materias(materias_texto))


def _revisar_repetidos(conexion, dni, email, propio_id=None):
    """Lanza ErrorValidacion si otro docente ya usa ese DNI o email."""
    for campo, columna, valor in (("DNI", "dni", dni),
                                  ("email", "email", email)):
        # La columna sale de esta lista fija, nunca del usuario.
        fila = conexion.execute(
            f"SELECT nombre, apellido FROM docentes WHERE {columna} = ? "
            "AND id IS NOT ?", (valor, propio_id)).fetchone()
        if fila:
            raise ErrorValidacion(
                f"Ya existe un docente con el {campo} {valor} "
                f"({fila['nombre']} {fila['apellido']}).")


def _guardar_materias(conexion, docente_id, nombres):
    """Reemplaza las materias del docente por las indicadas."""
    conexion.execute("DELETE FROM docente_materias WHERE docente_id = ?",
                     (docente_id,))
    for nombre in nombres:
        conexion.execute(
            "INSERT INTO docente_materias (docente_id, materia_id) "
            "VALUES (?, ?)",
            (docente_id, materias.obtener_o_crear(conexion, nombre)))


def alta(conexion, dni, nombre, apellido, email, materias_texto):
    """
    Da de alta un docente y lo devuelve.

    materias_texto: las materias separadas por comas.
    """
    dni, nombre, apellido, email, lista = _validar(
        dni, nombre, apellido, email, materias_texto)
    with transaccion(conexion):
        _revisar_repetidos(conexion, dni, email)
        docente_id = conexion.execute(
            "INSERT INTO docentes (dni, nombre, apellido, email) "
            "VALUES (?, ?, ?, ?)", (dni, nombre, apellido, email)).lastrowid
        _guardar_materias(conexion, docente_id, lista)
    return obtener(conexion, docente_id)


def modificar(conexion, docente_id, dni, nombre, apellido, email,
              materias_texto):
    """Cambia los datos de un docente y lo devuelve actualizado."""
    docente = buscar(conexion, docente_id)
    dni, nombre, apellido, email, lista = _validar(
        dni, nombre, apellido, email, materias_texto)
    with transaccion(conexion):
        _revisar_repetidos(conexion, dni, email, docente.id)
        conexion.execute(
            "UPDATE docentes SET dni = ?, nombre = ?, apellido = ?, "
            "email = ? WHERE id = ?",
            (dni, nombre, apellido, email, docente.id))
        _guardar_materias(conexion, docente.id, lista)
    return obtener(conexion, docente.id)


def eliminar(conexion, docente_id):
    """
    Da de baja un docente y lo devuelve.

    No se puede si está a cargo de algún curso: primero hay que asignar
    el curso a otro docente.
    """
    docente = buscar(conexion, docente_id)
    with transaccion(conexion):
        cursos = conexion.execute(
            "SELECT COUNT(*) FROM cursos WHERE docente_id = ?",
            (docente.id,)).fetchone()[0]
        if cursos:
            raise ErrorValidacion(
                f"{docente.nombre_completo} está a cargo de {cursos} "
                f"curso{'' if cursos == 1 else 's'}. Asigná otro docente "
                "antes de darlo de baja.")
        conexion.execute("DELETE FROM docentes WHERE id = ?", (docente.id,))
    return docente


def obtener(conexion, docente_id):
    """Devuelve el docente con ese id (con sus materias), o None."""
    fila = conexion.execute("SELECT * FROM docentes WHERE id = ?",
                            (docente_id,)).fetchone()
    if fila is None:
        return None
    return Docente.desde_fila(fila, _materias_de(conexion, fila["id"]))


def buscar(conexion, docente_id):
    """Como obtener, pero lanza ErrorValidacion si no existe."""
    docente = obtener(conexion, validar_id(docente_id, "El docente"))
    if docente is None:
        raise ErrorValidacion("El docente indicado no existe.")
    return docente


def listar(conexion):
    """
    Todos los docentes, ordenados por apellido, para la pantalla.

    Cada elemento es un diccionario con los datos del docente, sus
    materias, cuántos cursos tiene a cargo y si tiene cuenta de usuario
    con el mismo email.
    """
    filas = conexion.execute(
        "SELECT d.*, "
        "(SELECT COUNT(*) FROM cursos c WHERE c.docente_id = d.id) "
        "AS cursos, "
        "EXISTS (SELECT 1 FROM usuarios u WHERE u.email = d.email) "
        "AS tiene_cuenta "
        "FROM docentes d ORDER BY d.apellido, d.nombre").fetchall()
    return [{**dict(fila),
             "nombre_completo": f"{fila['nombre']} {fila['apellido']}",
             "tiene_cuenta": bool(fila["tiene_cuenta"]),
             "materias": _materias_de(conexion, fila["id"])}
            for fila in filas]
