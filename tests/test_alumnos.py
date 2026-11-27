"""Tests de servicios/alumnos.py: alta, búsqueda y listado."""
import pytest

from asistencia.servicios import alumnos
from asistencia.validaciones import ErrorValidacion


def test_alta_normaliza_nombre(con_alumnos):
    """El nombre y el apellido se guardan prolijos."""
    alumno = alumnos.buscar_por_dni(con_alumnos, "45123456")
    assert (alumno.nombre, alumno.apellido) == ("Juan", "Pérez")
    assert alumno.nombre_completo == "Juan Pérez"


@pytest.mark.parametrize("nombre, apellido", [
    ("", "Pérez"), ("Juan", "   "), ("Juan2", "Pérez"), ("Juan", "P@rez")])
def test_alta_con_nombre_invalido(conexion, nombre, apellido):
    """Con un nombre inválido no se da de alta a nadie."""
    with pytest.raises(ErrorValidacion):
        alumnos.alta(conexion, "40111222", nombre, apellido)
    assert alumnos.cantidad(conexion) == 0


def test_no_permite_dni_duplicado(con_alumnos):
    """El DNI es único, aunque se escriba con puntos."""
    with pytest.raises(ErrorValidacion, match="Ya existe"):
        alumnos.alta(con_alumnos, "45.123.456", "Otro", "Alumno")
    assert alumnos.cantidad(con_alumnos) == 2


def test_acepta_nombres_compuestos(conexion):
    """Se aceptan nombres con espacios, apóstrofos y guiones."""
    alumno = alumnos.alta(conexion, "40111222", "maría  josé",
                          "o'brien-núñez")
    assert (alumno.nombre, alumno.apellido) == ("María José",
                                                "O'Brien-Núñez")


def test_buscar_dni_inexistente(con_alumnos):
    """Buscar un DNI que no existe da un mensaje claro."""
    with pytest.raises(ErrorValidacion, match="No hay ningún alumno"):
        alumnos.buscar_por_dni(con_alumnos, "99999999")


def test_listar_ordena_por_apellido(con_alumnos):
    """El listado sale ordenado por apellido, respetando las tildes."""
    alumnos.alta(con_alumnos, "40111222", "Zoe", "Álvarez")
    apellidos = [a.apellido for a in alumnos.listar(con_alumnos)]
    assert apellidos == ["Álvarez", "Gómez", "Pérez"]
