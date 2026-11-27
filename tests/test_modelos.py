"""Tests de modelos.py: creación desde filas de la base y
propiedades."""
from contextlib import closing

from asistencia import bd
from asistencia.modelos import (Alumno, Curso, Docente, Horario,
                                RegistroAsistencia, Usuario)


def fila(conexion, sql, *parametros):
    """Ejecuta una consulta y devuelve la primera fila."""
    return conexion.execute(sql, parametros).fetchone()


def test_desde_fila_toma_solo_las_columnas_de_la_clase():
    """Las columnas extra de la consulta se ignoran."""
    with closing(bd.conectar(":memory:")) as conexion:
        datos = fila(conexion, "SELECT 1 AS id, '45123456' AS dni, "
                     "'Juan' AS nombre, 'Pérez' AS apellido, "
                     "'otra cosa' AS columna_extra")
        alumno = Alumno.desde_fila(datos)
    assert alumno == Alumno(1, "45123456", "Juan", "Pérez")
    assert alumno.nombre_completo == "Juan Pérez"


def test_registro_de_asistencia_convierte_manual_en_bool():
    """En la base 'manual' es 0/1; en el modelo es True/False."""
    with closing(bd.conectar(":memory:")) as conexion:
        datos = fila(conexion, "SELECT 1 AS id, 2 AS alumno_id, "
                     "'2026-11-06' AS fecha, 'AUSENTE' AS estado, "
                     "NULL AS hora, 1 AS manual")
        registro = RegistroAsistencia.desde_fila(datos)
    assert registro.manual is True and registro.hora is None


def test_propiedades_de_usuario():
    """El rol se consulta con propiedades fáciles de leer."""
    admin = Usuario(1, "a@b.com", "Ana", "Díaz", rol="administrador")
    alumno = Usuario(2, "c@d.com", "Juan", "Pérez", rol="alumno",
                     alumno_id=7)
    assert admin.es_administrador and not admin.es_alumno
    assert alumno.es_alumno and not alumno.es_administrador
    assert admin.nombre_completo == "Ana Díaz"


def test_nombres_de_curso_docente_y_horario():
    """Cada modelo sabe cómo mostrarse."""
    assert Curso(1, "Programación", 3, "A", 1).nombre_completo == \
        "Programación 3° A"
    assert Docente(1, "30111222", "Laura", "Sosa", "l@e.com",
                   ["Física"]).nombre_completo == "Laura Sosa"
    assert Horario(1, 1, 4, "08:00", "09:00", 1).nombre_dia == "Viernes"
