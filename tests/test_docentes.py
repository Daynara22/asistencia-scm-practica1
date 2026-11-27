"""Tests de servicios/docentes.py y servicios/materias.py."""
import pytest

from asistencia.servicios import docentes, materias, usuarios
from asistencia.validaciones import ErrorValidacion
from tests.conftest import DOCENTE, crear_curso


def alta(conexion, dni="30111222", email="laura@escuela.edu.ar",
         materias_texto="Matemática, Física"):
    """Da de alta un docente de prueba."""
    return docentes.alta(conexion, dni, "laura", "sosa", email,
                         materias_texto)


def test_alta_de_docente(conexion):
    """Se guarda con sus datos prolijos y sus materias ordenadas."""
    docente = alta(conexion, materias_texto="física, Matemática, física")
    assert docente.nombre_completo == "Laura Sosa"
    assert docente.materias == ["Física", "Matemática"]
    assert materias.listar(conexion) == ["Física", "Matemática"]


@pytest.mark.parametrize("campo, valor, mensaje", [
    ("dni", "12ab", "DNI"),
    ("email", "laura@", "email"),
    ("materias_texto", " , ", "al menos una materia"),
    ("materias_texto", "Matemática, @@", "materia"),
])
def test_alta_con_datos_invalidos(conexion, campo, valor, mensaje):
    """Cada dato se valida y no se guarda nada si alguno falla."""
    with pytest.raises(ErrorValidacion, match=mensaje):
        alta(conexion, **{campo: valor})
    assert docentes.listar(conexion) == []


def test_dni_y_email_unicos(conexion):
    """No puede haber dos docentes con el mismo DNI o email."""
    alta(conexion)
    with pytest.raises(ErrorValidacion, match="DNI"):
        alta(conexion, email="otra@escuela.edu.ar")
    with pytest.raises(ErrorValidacion, match="email"):
        alta(conexion, dni="30111333")


def test_materias_se_comparten(conexion):
    """La misma materia de dos docentes es una sola materia."""
    alta(conexion, materias_texto="Matemática")
    alta(conexion, dni="30111333", email="otra@escuela.edu.ar",
         materias_texto="matemática")
    assert materias.listar(conexion) == ["Matemática"]


def test_modificar_docente(conexion):
    """Se cambian los datos y se reemplazan las materias."""
    docente = alta(conexion)
    cambiado = docentes.modificar(conexion, docente.id, "30111222",
                                  "Laura", "Sosa Pérez",
                                  "laura@escuela.edu.ar", "Química")
    assert cambiado.apellido == "Sosa Pérez"
    assert cambiado.materias == ["Química"]


def test_modificar_con_email_de_otro(conexion):
    """No se puede usar el email de otro docente."""
    alta(conexion)
    otro = alta(conexion, dni="30111333", email="otra@escuela.edu.ar")
    with pytest.raises(ErrorValidacion, match="email"):
        docentes.modificar(conexion, otro.id, "30111333", "A", "B",
                           "laura@escuela.edu.ar", "Física")


def test_eliminar_docente(conexion):
    """Un docente sin cursos se puede dar de baja."""
    docente = alta(conexion)
    docentes.eliminar(conexion, docente.id)
    assert docentes.obtener(conexion, docente.id) is None


def test_no_elimina_docente_con_cursos(conexion):
    """Si está a cargo de un curso, no se puede dar de baja."""
    curso = crear_curso(conexion)
    with pytest.raises(ErrorValidacion, match="a cargo de 1 curso"):
        docentes.eliminar(conexion, curso.docente_id)


@pytest.mark.parametrize("docente_id", ["999", "abc", "", "-1"])
def test_docente_inexistente(conexion, docente_id):
    """Buscar un docente que no existe da error claro."""
    with pytest.raises(ErrorValidacion, match="no existe"):
        docentes.buscar(conexion, docente_id)


def test_listado_marca_si_tiene_cuenta(conexion):
    """El listado indica si hay una cuenta de usuario con el mismo
    email."""
    usuarios.registrar_docente(conexion, DOCENTE["email"], "María",
                               "González", DOCENTE["clave"],
                               DOCENTE["clave"])
    alta(conexion, email=DOCENTE["email"])
    alta(conexion, dni="30111333", email="sin.cuenta@escuela.edu.ar")
    cuentas = {d["email"]: d["tiene_cuenta"]
               for d in docentes.listar(conexion)}
    assert cuentas == {DOCENTE["email"]: True,
                       "sin.cuenta@escuela.edu.ar": False}
