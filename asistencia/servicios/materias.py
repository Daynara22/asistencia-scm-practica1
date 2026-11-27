"""
materias.py - Materias que dictan los docentes y que tienen los horarios.

Las materias no tienen pantalla propia: se crean solas cuando se escriben
en un docente o en un horario. El nombre no distingue mayúsculas
("matemática" y "Matemática" son la misma materia).
"""
from asistencia.validaciones import validar_texto


def obtener_o_crear(conexion, nombre):
    """
    Devuelve el id de la materia, creándola si no existe.

    Se usa dentro de la transacción del docente o del horario.
    """
    nombre = validar_texto(nombre, "materia")
    fila = conexion.execute("SELECT id FROM materias WHERE nombre = ?",
                            (nombre,)).fetchone()
    if fila:
        return fila["id"]
    return conexion.execute("INSERT INTO materias (nombre) VALUES (?)",
                            (nombre,)).lastrowid


def listar(conexion):
    """Nombres de todas las materias, en orden alfabético."""
    return [fila["nombre"] for fila in conexion.execute(
        "SELECT nombre FROM materias ORDER BY nombre")]
