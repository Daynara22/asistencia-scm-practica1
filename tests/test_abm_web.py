"""Tests de las pantallas de ABM: alumnos, docentes, cursos y
horarios."""
import pytest

from tests.conftest import CURSO_ID, datos_alumno

DOCENTE_NUEVO = {"dni": "30222333", "nombre": "Pablo", "apellido": "Ríos",
                 "email": "pablo@escuela.edu.ar", "materias": "Redes"}
CURSO_NUEVO = {"nombre": "Electrónica", "anio": "2", "division": "B",
               "docente_id": "1"}
BLOQUE = {"curso_id": str(CURSO_ID), "dia": "0", "hora_inicio": "08:00",
          "hora_fin": "09:20", "materia": "Matemática"}


@pytest.mark.parametrize("ruta", ["/docentes", "/cursos", "/horarios"])
def test_pantallas_abren(cliente, ruta):
    """Las pantallas nuevas abren para el administrador."""
    assert cliente.get(ruta).status_code == 200


# ---------------- Alumnos ----------------

def test_alta_alumno_muestra_curso_y_email(cliente):
    """El listado de alumnos muestra el curso."""
    r = cliente.post("/alumnos", data=datos_alumno("45123456", "Juan",
                                                   "Pérez"),
                     follow_redirects=True)
    assert "Se dio de alta a Juan Pérez" in r.text
    assert "Programación 3° A" in r.text


def test_alta_alumno_sin_curso(cliente):
    """Sin curso no se da de alta."""
    datos = {**datos_alumno("45123456", "Juan", "Pérez"), "curso_id": ""}
    r = cliente.post("/alumnos", data=datos)
    assert r.status_code == 400 and "Elegí el curso" in r.text


def test_editar_alumno(cliente):
    """El formulario se carga con los datos y guarda los cambios."""
    cliente.post("/alumnos", data=datos_alumno("45123456", "Juan", "Pérez"))
    r = cliente.get("/alumnos?editar=1")
    assert "Editando" in r.text and 'value="45123456"' in r.text
    datos = {**datos_alumno("45123456", "Juan", "Paredes")}
    r = cliente.post("/alumnos/1", data=datos, follow_redirects=True)
    assert "Se guardaron los cambios de Juan Paredes" in r.text


def test_editar_alumno_con_error_vuelve_al_formulario(cliente):
    """Si un dato está mal, se ve el error y sigue en modo edición."""
    cliente.post("/alumnos", data=datos_alumno("45123456", "Juan", "Pérez"))
    datos = {**datos_alumno("45123456", "Juan", "Pérez"), "email": "mal@"}
    r = cliente.post("/alumnos/1", data=datos)
    assert r.status_code == 400
    assert "El email no es válido" in r.text and "Editando" in r.text


def test_editar_alumno_inexistente(cliente):
    """Editar un id que no existe muestra el error."""
    r = cliente.get("/alumnos?editar=999")
    assert r.status_code == 404 and "no existe" in r.text


def test_baja_de_alumno(cliente):
    """El administrador da de baja un alumno."""
    cliente.post("/alumnos", data=datos_alumno("45123456", "Juan", "Pérez"))
    r = cliente.post("/alumnos/1/eliminar", follow_redirects=True)
    assert "Se dio de baja a Juan Pérez" in r.text
    assert "Todavía no hay alumnos" in r.text


def test_filtrar_alumnos_por_curso(cliente):
    """El filtro por curso muestra solo sus alumnos."""
    cliente.post("/cursos", data=CURSO_NUEVO)
    cliente.post("/alumnos", data=datos_alumno("45123456", "Juan", "Pérez"))
    cliente.post("/alumnos", data=datos_alumno("40111222", "Ana", "Díaz",
                                               curso_id=2))
    r = cliente.get("/alumnos?curso=2")
    assert "<td>Ana</td>" in r.text and "<td>Juan</td>" not in r.text


# ---------------- Docentes ----------------

def test_abm_docente(cliente):
    """Alta, edición y baja de un docente desde la pantalla."""
    r = cliente.post("/docentes", data=DOCENTE_NUEVO, follow_redirects=True)
    assert "Se dio de alta a Pablo Ríos" in r.text and "Redes" in r.text

    r = cliente.get("/docentes?editar=2")
    assert "Editando" in r.text and 'value="Redes"' in r.text
    r = cliente.post("/docentes/2",
                     data={**DOCENTE_NUEVO, "materias": "Redes, Sistemas"},
                     follow_redirects=True)
    assert "Redes, Sistemas" in r.text

    r = cliente.post("/docentes/2/eliminar", follow_redirects=True)
    assert "Se dio de baja a Pablo Ríos" in r.text


def test_docente_con_dni_repetido(cliente):
    """La pantalla avisa si el DNI ya existe."""
    cliente.post("/docentes", data=DOCENTE_NUEVO)
    r = cliente.post("/docentes", data={**DOCENTE_NUEVO,
                                        "email": "otro@escuela.edu.ar"})
    assert r.status_code == 400 and "Ya existe un docente" in r.text


def test_no_baja_docente_a_cargo_de_curso(cliente):
    """El docente del curso de prueba no se puede dar de baja."""
    r = cliente.post("/docentes/1/eliminar")
    assert r.status_code == 400 and "a cargo de 1 curso" in r.text


# ---------------- Cursos ----------------

def test_abm_curso(cliente):
    """Alta, edición y baja de un curso."""
    r = cliente.post("/cursos", data=CURSO_NUEVO, follow_redirects=True)
    assert "Se dio de alta el curso Electrónica 2° B" in r.text
    r = cliente.get("/cursos?editar=2")
    assert "Editando" in r.text
    r = cliente.post("/cursos/2", data={**CURSO_NUEVO, "division": "C"},
                     follow_redirects=True)
    assert "Electrónica 2° C" in r.text
    r = cliente.post("/cursos/2/eliminar", follow_redirects=True)
    assert "Se dio de baja el curso Electrónica 2° C" in r.text


def test_curso_con_anio_invalido(cliente):
    """El año fuera de rango se rechaza."""
    r = cliente.post("/cursos", data={**CURSO_NUEVO, "anio": "9"})
    assert r.status_code == 400 and "entre 1 y 7" in r.text


# ---------------- Horarios ----------------

def test_abm_horario(cliente):
    """Agregar, editar y quitar un bloque de horario."""
    r = cliente.post("/horarios", data=BLOQUE, follow_redirects=True)
    assert "Se agregó el bloque del lunes de 08:00 a 09:20" in r.text
    r = cliente.get("/horarios?editar=1")
    assert "Editando" in r.text and 'value="Matemática"' in r.text
    r = cliente.post("/horarios/1", data={**BLOQUE, "hora_fin": "10:00"},
                     follow_redirects=True)
    assert "08:00 a 10:00" in r.text
    r = cliente.post("/horarios/1/eliminar", follow_redirects=True)
    assert "Se quitó el bloque" in r.text


def test_horario_superpuesto_en_pantalla(cliente):
    """La pantalla explica con qué bloque se superpone."""
    cliente.post("/horarios", data=BLOQUE)
    r = cliente.post("/horarios", data={**BLOQUE, "hora_inicio": "09:00",
                                        "hora_fin": "10:00",
                                        "materia": "Física"})
    assert r.status_code == 400
    assert "Se superpone con Matemática del lunes" in r.text


def test_filtrar_horarios_por_curso(cliente):
    """El filtro por curso muestra solo sus bloques."""
    cliente.post("/cursos", data=CURSO_NUEVO)
    cliente.post("/horarios", data=BLOQUE)
    cliente.post("/horarios", data={**BLOQUE, "curso_id": "2",
                                    "materia": "Física"})
    r = cliente.get("/horarios?curso=2")
    assert "Física" in r.text and "Matemática</td>" not in r.text


# ---------------- Permisos ----------------

@pytest.mark.parametrize("ruta", ["/docentes", "/cursos", "/horarios"])
def test_docente_ve_los_listados_sin_formularios(cliente_docente, ruta):
    """El docente ve los listados pero no puede editarlos."""
    r = cliente_docente.get(ruta)
    assert r.status_code == 200
    assert "Dar de alta" not in r.text and "Agregar bloque" not in r.text


@pytest.mark.parametrize("ruta", [
    "/docentes", "/docentes/1", "/docentes/1/eliminar",
    "/cursos", "/cursos/1", "/cursos/1/eliminar",
    "/horarios", "/horarios/1", "/horarios/1/eliminar",
    "/alumnos/1/eliminar",
])
def test_docente_no_puede_modificar(cliente_docente, ruta):
    """Solo el administrador modifica docentes, cursos y horarios, y da
    de baja alumnos."""
    assert cliente_docente.post(ruta, data={}).status_code == 403


def test_docente_si_puede_editar_alumnos(cliente_docente):
    """El docente da de alta y edita alumnos (pero no los da de baja)."""
    cliente_docente.post("/alumnos",
                         data=datos_alumno("45123456", "Juan", "Pérez"))
    r = cliente_docente.post("/alumnos/1",
                             data=datos_alumno("45123456", "Juan", "Paz"),
                             follow_redirects=True)
    assert "Se guardaron los cambios de Juan Paz" in r.text
    assert "Dar de baja" not in r.text


@pytest.mark.parametrize("ruta", ["/docentes", "/cursos", "/horarios"])
def test_alumno_no_ve_los_abm(cliente_alumno, ruta):
    """El alumno no entra a ninguna pantalla de ABM."""
    assert cliente_alumno.get(ruta).status_code == 403


@pytest.mark.parametrize("ruta", ["/docentes?editar=999",
                                  "/cursos?editar=999",
                                  "/horarios?editar=abc"])
def test_editar_inexistente(cliente, ruta):
    """Editar algo que no existe muestra el error y el listado."""
    r = cliente.get(ruta)
    assert r.status_code == 404 and "no existe" in r.text
