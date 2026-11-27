"""Tests de servicios/cursos.py."""
import pytest

from asistencia.servicios import cursos, docentes, horarios
from asistencia.validaciones import ErrorValidacion
from tests.conftest import alta_alumno, crear_curso


@pytest.fixture
def docente(conexion):
    """Un docente para poner a cargo de los cursos."""
    return docentes.alta(conexion, "30111222", "Laura", "Sosa",
                         "laura@escuela.edu.ar", "Programación")


def test_alta_de_curso(conexion, docente):
    """El curso se guarda con su nombre completo."""
    curso = cursos.alta(conexion, "programación", "3", " a", docente.id)
    assert curso.nombre_completo == "Programación 3° A"
    listado = cursos.listar(conexion)
    assert listado[0]["docente"] == "Laura Sosa"
    assert listado[0]["alumnos"] == 0


@pytest.mark.parametrize("anio, division, docente_id, mensaje", [
    ("0", "A", "1", "entre 1 y 7"),
    ("8", "A", "1", "entre 1 y 7"),
    ("tres", "A", "1", "número"),
    ("3", "", "1", "división"),
    ("3", "ABCD", "1", "división"),
    ("3", "A", "", "docente a cargo"),
    ("3", "A", "99", "no existe"),
])
def test_alta_con_datos_invalidos(conexion, docente, anio, division,
                                  docente_id, mensaje):
    """Año, división y docente se validan."""
    with pytest.raises(ErrorValidacion, match=mensaje):
        cursos.alta(conexion, "Programación", anio, division, docente_id)
    assert cursos.listar(conexion) == []


def test_curso_repetido(conexion, docente):
    """No puede haber dos cursos con igual nombre, año y división."""
    cursos.alta(conexion, "Programación", 3, "A", docente.id)
    with pytest.raises(ErrorValidacion, match="Ya existe el curso"):
        cursos.alta(conexion, "Programación", 3, "a", docente.id)
    cursos.alta(conexion, "Programación", 3, "B", docente.id)   # otra div.


def test_modificar_curso(conexion, docente):
    """Se puede cambiar el docente a cargo y la división."""
    curso = cursos.alta(conexion, "Programación", 3, "A", docente.id)
    otro = docentes.alta(conexion, "30111333", "Pablo", "Ríos",
                         "pablo@escuela.edu.ar", "Redes")
    cambiado = cursos.modificar(conexion, curso.id, "Programación", 3, "C",
                                otro.id)
    assert cambiado.nombre_completo == "Programación 3° C"
    assert cursos.obtener(conexion, curso.id).docente_id == otro.id


def test_modificar_a_un_curso_que_ya_existe(conexion, docente):
    """No se puede modificar un curso para que quede igual a otro."""
    cursos.alta(conexion, "Programación", 3, "A", docente.id)
    curso_b = cursos.alta(conexion, "Programación", 3, "B", docente.id)
    with pytest.raises(ErrorValidacion, match="Ya existe"):
        cursos.modificar(conexion, curso_b.id, "Programación", 3, "A",
                         docente.id)


def test_eliminar_curso_con_horarios(conexion, docente):
    """Al dar de baja un curso se borran sus horarios."""
    curso = cursos.alta(conexion, "Programación", 3, "A", docente.id)
    horarios.alta(conexion, curso.id, 0, "08:00", "09:20", "Programación")
    cursos.eliminar(conexion, curso.id)
    assert cursos.obtener(conexion, curso.id) is None
    assert horarios.listar(conexion) == []


def test_no_elimina_curso_con_alumnos(con_curso):
    """Un curso con alumnos no se puede dar de baja."""
    curso = cursos.listar(con_curso)[0]
    alta_alumno(con_curso, "45123456", "Juan", "Pérez", curso["id"])
    with pytest.raises(ErrorValidacion, match="tiene 1 alumno"):
        cursos.eliminar(con_curso, curso["id"])


def test_listado_ordenado_por_anio_y_division(conexion):
    """Los cursos salen ordenados por año y división."""
    crear_curso(conexion, division="B")
    crear_curso(conexion, nombre="Arte", division="A")
    nombres = [c["nombre_completo"] for c in cursos.listar(conexion)]
    assert nombres == ["Arte 3° A", "Programación 3° B"]
