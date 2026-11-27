"""Tests de servicios/horarios.py: validación y superposición."""
import pytest

from asistencia.servicios import horarios
from asistencia.validaciones import ErrorValidacion
from tests.conftest import CURSO_ID, crear_curso

LUNES, MARTES = 0, 1


def alta(conexion, inicio, fin, dia=LUNES, materia="Matemática",
         curso_id=CURSO_ID):
    """Agrega un bloque de horario de prueba."""
    return horarios.alta(conexion, curso_id, dia, inicio, fin, materia)


def test_alta_de_horario(con_curso):
    """El bloque se guarda con su día, horas y materia."""
    horario = alta(con_curso, "08:00", "09:20")
    assert horario.nombre_dia == "Lunes"
    listado = horarios.listar(con_curso)
    assert listado[0]["materia"] == "Matemática"
    assert listado[0]["curso"] == "Programación 3° A"


@pytest.mark.parametrize("inicio, fin, dia, mensaje", [
    ("09:00", "08:00", LUNES, "posterior"),
    ("08:00", "08:00", LUNES, "posterior"),
    ("25:00", "26:00", LUNES, "no es válida"),
    ("08:00", "09:00", 7, "entre 0 y 6"),
    ("08:00", "09:00", "", "día"),
])
def test_alta_con_datos_invalidos(con_curso, inicio, fin, dia, mensaje):
    """Horas y día se validan."""
    with pytest.raises(ErrorValidacion, match=mensaje):
        alta(con_curso, inicio, fin, dia)
    assert horarios.listar(con_curso) == []


def test_curso_obligatorio_y_existente(con_curso):
    """El horario tiene que ser de un curso que exista."""
    with pytest.raises(ErrorValidacion, match="Elegí el curso"):
        alta(con_curso, "08:00", "09:00", curso_id="")
    with pytest.raises(ErrorValidacion, match="no existe"):
        alta(con_curso, "08:00", "09:00", curso_id=99)


@pytest.mark.parametrize("inicio, fin", [
    ("08:30", "09:30"),     # empieza en el medio
    ("07:30", "08:30"),     # termina en el medio
    ("08:15", "08:45"),     # queda adentro
    ("07:00", "10:00"),     # lo cubre entero
    ("08:00", "09:00"),     # el mismo horario
])
def test_no_se_superponen(con_curso, inicio, fin):
    """Dos bloques del mismo curso y día no pueden pisarse."""
    alta(con_curso, "08:00", "09:00")
    with pytest.raises(ErrorValidacion, match="Se superpone con Matemática"):
        alta(con_curso, inicio, fin, materia="Física")
    assert len(horarios.listar(con_curso)) == 1


def test_bloques_que_se_tocan_si_se_permiten(con_curso):
    """Uno puede empezar justo cuando termina el otro."""
    alta(con_curso, "08:00", "09:00")
    alta(con_curso, "09:00", "10:00", materia="Física")
    alta(con_curso, "07:00", "08:00", materia="Lengua")
    assert len(horarios.listar(con_curso)) == 3


def test_otro_dia_u_otro_curso_no_se_superpone(con_curso):
    """La superposición solo cuenta en el mismo curso y el mismo día."""
    otro = crear_curso(con_curso, division="B")
    alta(con_curso, "08:00", "09:00")
    alta(con_curso, "08:00", "09:00", dia=MARTES)
    alta(con_curso, "08:00", "09:00", curso_id=otro.id)
    assert len(horarios.listar(con_curso)) == 3
    assert len(horarios.listar(con_curso, otro.id)) == 1


def test_modificar_sin_superponerse_consigo_mismo(con_curso):
    """Al modificar un bloque, no se compara contra sí mismo."""
    horario = alta(con_curso, "08:00", "09:00")
    cambiado = horarios.modificar(con_curso, horario.id, CURSO_ID, LUNES,
                                  "08:30", "09:30", "Matemática")
    assert (cambiado.hora_inicio, cambiado.hora_fin) == ("08:30", "09:30")


def test_modificar_hacia_una_superposicion(con_curso):
    """Al modificar tampoco se puede pisar otro bloque."""
    alta(con_curso, "08:00", "09:00")
    segundo = alta(con_curso, "10:00", "11:00", materia="Física")
    with pytest.raises(ErrorValidacion, match="Se superpone"):
        horarios.modificar(con_curso, segundo.id, CURSO_ID, LUNES,
                           "08:30", "10:30", "Física")


def test_eliminar_horario(con_curso):
    """Un bloque se puede quitar."""
    horario = alta(con_curso, "08:00", "09:00")
    horarios.eliminar(con_curso, horario.id)
    assert horarios.listar(con_curso) == []
    with pytest.raises(ErrorValidacion):
        horarios.eliminar(con_curso, horario.id)


def test_listado_ordenado_por_dia_y_hora(con_curso):
    """El listado sale ordenado por día y hora de inicio."""
    alta(con_curso, "10:00", "11:00", dia=MARTES)
    alta(con_curso, "10:00", "11:00")
    alta(con_curso, "08:00", "09:00")
    orden = [(h["nombre_dia"], h["hora_inicio"])
             for h in horarios.listar(con_curso)]
    assert orden == [("Lunes", "08:00"), ("Lunes", "10:00"),
                     ("Martes", "10:00")]
