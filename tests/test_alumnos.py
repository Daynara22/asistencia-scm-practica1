"""Tests de servicios/alumnos.py: alta, baja, modificación y listado."""
import pytest

from asistencia.servicios import alumnos, asistencias, usuarios
from asistencia.validaciones import ErrorValidacion
from tests.conftest import (CLAVE, CURSO_ID, a_las, alta_alumno,
                            crear_curso)


def test_alta_normaliza_nombre(con_alumnos):
    """El nombre y el apellido se guardan prolijos, con email y
    curso."""
    alumno = alumnos.buscar_por_dni(con_alumnos, "45123456")
    assert (alumno.nombre, alumno.apellido) == ("Juan", "Pérez")
    assert alumno.nombre_completo == "Juan Pérez"
    assert alumno.email == "45123456@alumnos.edu.ar"
    assert alumno.curso_id == CURSO_ID


@pytest.mark.parametrize("nombre, apellido", [
    ("", "Pérez"), ("Juan", "   "), ("Juan2", "Pérez"), ("Juan", "P@rez")])
def test_alta_con_nombre_invalido(con_curso, nombre, apellido):
    """Con un nombre inválido no se da de alta a nadie."""
    with pytest.raises(ErrorValidacion):
        alta_alumno(con_curso, "40111222", nombre, apellido)
    assert alumnos.cantidad(con_curso) == 0


def test_alta_exige_email_valido(con_curso):
    """Al dar de alta, el email es obligatorio y tiene que ser válido."""
    for email in ("", "juan@", "sin-arroba"):
        with pytest.raises(ErrorValidacion, match="email"):
            alumnos.alta(con_curso, "40111222", "Juan", "Pérez", email,
                         CURSO_ID)
    assert alumnos.cantidad(con_curso) == 0


@pytest.mark.parametrize("curso_id, mensaje", [
    ("", "Elegí el curso"), ("99", "no existe"), ("abc", "no existe")])
def test_alta_exige_curso_existente(con_curso, curso_id, mensaje):
    """Al dar de alta, el curso es obligatorio y tiene que existir."""
    with pytest.raises(ErrorValidacion, match=mensaje):
        alumnos.alta(con_curso, "40111222", "Juan", "Pérez",
                     "juan@alumnos.edu.ar", curso_id)


def test_no_permite_dni_duplicado(con_alumnos):
    """El DNI es único, aunque se escriba con puntos."""
    with pytest.raises(ErrorValidacion, match="Ya existe un alumno con el "
                                              "DNI"):
        alumnos.alta(con_alumnos, "45.123.456", "Otro", "Alumno",
                     "otro@alumnos.edu.ar", CURSO_ID)
    assert alumnos.cantidad(con_alumnos) == 2


def test_no_permite_email_duplicado(con_alumnos):
    """El email del alumno también es único."""
    with pytest.raises(ErrorValidacion, match="email"):
        alumnos.alta(con_alumnos, "40111222", "Otro", "Alumno",
                     "45123456@ALUMNOS.edu.ar", CURSO_ID)


def test_acepta_nombres_compuestos(con_curso):
    """Se aceptan nombres con espacios, apóstrofos y guiones."""
    alumno = alta_alumno(con_curso, "40111222", "maría  josé",
                         "o'brien-núñez")
    assert (alumno.nombre, alumno.apellido) == ("María José",
                                                "O'Brien-Núñez")


def test_buscar_dni_inexistente(con_alumnos):
    """Buscar un DNI que no existe da un mensaje claro."""
    with pytest.raises(ErrorValidacion, match="No hay ningún alumno"):
        alumnos.buscar_por_dni(con_alumnos, "99999999")


def test_listar_ordena_por_apellido(con_alumnos):
    """El listado sale ordenado por apellido, respetando las tildes."""
    alta_alumno(con_alumnos, "40111222", "Zoe", "Álvarez")
    apellidos = [a.apellido for a in alumnos.listar(con_alumnos)]
    assert apellidos == ["Álvarez", "Gómez", "Pérez"]


def test_listar_por_curso(con_alumnos):
    """Se puede listar solo los alumnos de un curso."""
    otro = crear_curso(con_alumnos, division="B")
    alta_alumno(con_alumnos, "40111222", "Zoe", "Álvarez", otro.id)
    assert [a.dni for a in alumnos.listar(con_alumnos, otro.id)] == \
        ["40111222"]
    assert len(alumnos.listar(con_alumnos, CURSO_ID)) == 2


# ---------------- Modificación ----------------

def test_modificar_alumno(con_alumnos):
    """Se cambian todos los datos del alumno."""
    juan = alumnos.buscar_por_dni(con_alumnos, "45123456")
    otro = crear_curso(con_alumnos, division="B")
    alumnos.modificar(con_alumnos, juan.id, "45123457", "juan carlos",
                      "pérez", "jc@alumnos.edu.ar", otro.id)
    cambiado = alumnos.obtener(con_alumnos, juan.id)
    assert cambiado.dni == "45123457"
    assert cambiado.nombre == "Juan Carlos"
    assert (cambiado.email, cambiado.curso_id) == ("jc@alumnos.edu.ar",
                                                   otro.id)


def test_modificar_sin_email_ni_curso(con_alumnos):
    """Al modificar, email y curso son opcionales (alumnos viejos)."""
    juan = alumnos.buscar_por_dni(con_alumnos, "45123456")
    alumnos.modificar(con_alumnos, juan.id, "45123456", "Juan", "Pérez",
                      "", "")
    cambiado = alumnos.obtener(con_alumnos, juan.id)
    assert cambiado.email is None and cambiado.curso_id is None


def test_modificar_conserva_su_propio_dni(con_alumnos):
    """Guardar sin cambiar el DNI no lo cuenta como repetido."""
    juan = alumnos.buscar_por_dni(con_alumnos, "45123456")
    alumnos.modificar(con_alumnos, juan.id, "45123456", "Juan", "Pérez",
                      juan.email, CURSO_ID)


def test_modificar_a_un_dni_de_otro(con_alumnos):
    """No se puede cambiar el DNI por el de otro alumno."""
    juan = alumnos.buscar_por_dni(con_alumnos, "45123456")
    with pytest.raises(ErrorValidacion, match="Ana Gómez"):
        alumnos.modificar(con_alumnos, juan.id, "1234567", "Juan", "Pérez",
                          "", "")


def test_modificar_actualiza_la_cuenta(con_alumnos):
    """Si el alumno tiene cuenta, el nombre de la cuenta también
    cambia."""
    cuenta = usuarios.crear_cuenta_alumno(
        con_alumnos, "45123456", "juan@alumnos.edu.ar", CLAVE, CLAVE)
    alumnos.modificar(con_alumnos, cuenta.alumno_id, "45123456", "Juan",
                      "Paredes", "", "")
    assert usuarios.obtener(con_alumnos, cuenta.id).apellido == "Paredes"


def test_modificar_alumno_inexistente(con_alumnos):
    """Modificar un id que no existe da error."""
    with pytest.raises(ErrorValidacion, match="no existe"):
        alumnos.modificar(con_alumnos, 999, "40111222", "A", "B", "", "")


# ---------------- Baja ----------------

def test_eliminar_alumno_borra_su_asistencia_y_cuenta(con_alumnos):
    """La baja borra al alumno, sus registros y su cuenta."""
    asistencias.registrar(con_alumnos, "45123456", ahora=a_las(8, 0))
    cuenta = usuarios.crear_cuenta_alumno(
        con_alumnos, "45123456", "juan@alumnos.edu.ar", CLAVE, CLAVE)

    eliminado = alumnos.eliminar(con_alumnos, cuenta.alumno_id)

    assert eliminado.nombre_completo == "Juan Pérez"
    assert alumnos.cantidad(con_alumnos) == 1
    assert usuarios.obtener(con_alumnos, cuenta.id) is None
    total = con_alumnos.execute(
        "SELECT COUNT(*) FROM asistencias").fetchone()[0]
    assert total == 0


def test_eliminar_alumno_inexistente(con_alumnos):
    """Dar de baja un id que no existe da error y no borra nada."""
    with pytest.raises(ErrorValidacion):
        alumnos.eliminar(con_alumnos, "999")
    assert alumnos.cantidad(con_alumnos) == 2
