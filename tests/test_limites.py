"""
Tests del límite de faltas (servicios/limites.py) y de sus alertas.

Cubre el cálculo de faltas (ausentes y valor de la tardanza), el
límite general y por curso, los estados normal / cerca / superado y
cómo se muestran las alertas en las pantallas.
"""
from contextlib import closing
from datetime import date
from fractions import Fraction

import pytest

from asistencia import bd
from asistencia.servicios import asistencias, cursos, informes, limites
from asistencia.validaciones import ErrorValidacion
from tests.conftest import (CURSO_ID, HOY, a_las, alta_alumno, crear_curso,
                            datos_alumno)

JUAN = "45123456"


def faltar(conexion, dni, cantidad, desde=1):
    """Carga 'cantidad' ausencias del alumno en días de noviembre."""
    for dia in range(desde, desde + cantidad):
        asistencias.carga_manual(conexion, dni, f"2026-11-{dia:02d}",
                                 "AUSENTE", "", hoy=HOY)


def llegar_tarde(conexion, dni, cantidad, desde=20):
    """Registra 'cantidad' tardanzas del alumno en días de octubre."""
    for dia in range(desde, desde + cantidad):
        asistencias.registrar(conexion, dni,
                              ahora=a_las(9, 0, date(2026, 10, dia)))


def situacion(conexion, dni=JUAN):
    """Situación del alumno respecto del límite."""
    return informes.informe_alumno(conexion, dni)["situacion"]


# ----------------------------------------------------------------------
# Estados
# ----------------------------------------------------------------------

@pytest.mark.parametrize("faltas, estado", [
    (0, limites.NORMAL),
    (7, limites.NORMAL),          # 70 %
    (7.5, limites.CERCA),         # 75 % justo: empieza la alerta
    (9, limites.CERCA),
    (10, limites.CERCA),          # en el límite: todavía no lo superó
    (10.25, limites.SUPERADO),
    (14, limites.SUPERADO),
])
def test_evaluar_estados(faltas, estado):
    """Normal hasta el 75 %, cerca hasta el límite, superado después."""
    assert limites.evaluar(Fraction(str(faltas)), 10)["estado"] == estado


def test_evaluar_datos_para_mostrar():
    """El resultado trae porcentaje, faltas restantes y mensaje."""
    resultado = limites.evaluar(8, 10)
    assert resultado["porcentaje_limite"] == 80.0
    assert resultado["restantes"] == "2"
    assert "8 de 10 faltas (80 %)" in resultado["mensaje"]
    superado = limites.evaluar(12, 10)
    assert superado["restantes"] == "0"
    assert "Superó el límite" in superado["mensaje"]


@pytest.mark.parametrize("valor, esperado", [
    ("0", None), ("0.25", 4), ("0.5", 2), ("1", 1)])
def test_tardanzas_por_falta(valor, esperado):
    """La configuración se muestra como 'N tardanzas = 1 falta'."""
    assert limites.tardanzas_por_falta(valor) == esperado


@pytest.mark.parametrize("valor, tardanzas, faltas", [
    ("0.25", 8, 2), ("0.25", 3, 0.75), ("0.5", 5, 2.5), ("1", 3, 3),
    ("0", 10, 0)])
def test_equivalencia_de_tardanzas(valor, tardanzas, faltas):
    """Con 4 tardanzas = 1 falta, 8 tardanzas son 2 faltas (y así)."""
    assert float(limites.calcular_faltas(0, tardanzas, valor)) == faltas


def test_mostrar_numero():
    """Los enteros se muestran sin decimales."""
    assert limites.mostrar_numero(3) == "3"
    assert limites.mostrar_numero(2.5) == "2.5"
    assert limites.mostrar_numero(0.25) == "0.25"


# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------

def test_valores_por_defecto(conexion):
    """Por defecto: 10 faltas y la tardanza no suma."""
    assert limites.limite_general(conexion) == 10
    assert limites.valor_tardanza(conexion) == "0"


def test_cambiar_configuracion(conexion):
    """El administrador cambia el límite y el valor de la tardanza."""
    assert limites.cambiar_configuracion(conexion, "15", "0.5") == \
        (15, "0.5")
    assert limites.limite_general(conexion) == 15
    assert limites.valor_tardanza(conexion) == "0.5"


@pytest.mark.parametrize("limite, tardanza, mensaje", [
    ("0", "0", "entre 1 y 365"),
    ("-3", "0", "entre 1 y 365"),
    ("diez", "0", "número"),
    ("", "0", "límite"),
    ("10", "0.3", "tardanzas equivalen"),
])
def test_configuracion_invalida(conexion, limite, tardanza, mensaje):
    """Valores fuera de rango no se guardan."""
    with pytest.raises(ErrorValidacion, match=mensaje):
        limites.cambiar_configuracion(conexion, limite, tardanza)
    assert limites.limite_general(conexion) == 10


def test_limite_del_curso_reemplaza_al_general(con_curso):
    """Un curso con límite propio usa ese; los demás, el general."""
    curso = cursos.obtener(con_curso, CURSO_ID)
    cursos.modificar(con_curso, curso.id, curso.nombre, curso.anio,
                     curso.division, curso.docente_id, "4")
    otro = crear_curso(con_curso, division="B")
    assert limites.limite_para(con_curso, CURSO_ID) == 4
    assert limites.limite_para(con_curso, otro.id) == 10
    assert limites.limite_para(con_curso, None) == 10


def test_quitar_limite_del_curso(con_curso):
    """Dejar el límite vacío vuelve al general."""
    curso = cursos.obtener(con_curso, CURSO_ID)
    cursos.modificar(con_curso, curso.id, curso.nombre, curso.anio,
                     curso.division, curso.docente_id, "4")
    cursos.modificar(con_curso, curso.id, curso.nombre, curso.anio,
                     curso.division, curso.docente_id, "")
    assert cursos.obtener(con_curso, CURSO_ID).limite_faltas is None


@pytest.mark.parametrize("limite", ["0", "400", "x"])
def test_limite_de_curso_invalido(con_curso, limite):
    """El límite del curso también se valida."""
    with pytest.raises(ErrorValidacion):
        cursos.alta(con_curso, "Arte", 1, "A", 1, limite)


# ----------------------------------------------------------------------
# Cálculo de faltas de un alumno
# ----------------------------------------------------------------------

def test_cada_ausencia_es_una_falta(con_alumnos):
    """Las ausencias cuentan como faltas; las tardanzas, por defecto
    no."""
    faltar(con_alumnos, JUAN, 3)
    llegar_tarde(con_alumnos, JUAN, 4)
    resultado = situacion(con_alumnos)
    assert resultado["faltas_texto"] == "3"
    assert resultado["estado"] == limites.NORMAL


@pytest.mark.parametrize("valor, esperado", [
    ("0.25", "4"), ("0.5", "5"), ("1", "7")])
def test_tardanzas_suman_segun_configuracion(con_alumnos, valor, esperado):
    """3 ausencias + 4 tardanzas, con cada valor posible de tardanza."""
    faltar(con_alumnos, JUAN, 3)
    llegar_tarde(con_alumnos, JUAN, 4)
    limites.cambiar_configuracion(con_alumnos, "10", valor)
    assert situacion(con_alumnos)["faltas_texto"] == esperado


def test_media_falta_se_muestra_con_decimal(con_alumnos):
    """Una tardanza que vale 1/2 deja faltas con decimales."""
    llegar_tarde(con_alumnos, JUAN, 3)
    limites.cambiar_configuracion(con_alumnos, "10", "0.5")
    assert situacion(con_alumnos)["faltas_texto"] == "1.5"


def test_alerta_cerca_del_limite(con_alumnos):
    """Al llegar al 75 % del límite aparece la alerta."""
    limites.cambiar_configuracion(con_alumnos, "4", "0")
    faltar(con_alumnos, JUAN, 2)
    assert situacion(con_alumnos)["estado"] == limites.NORMAL
    faltar(con_alumnos, JUAN, 1, desde=3)
    assert situacion(con_alumnos)["estado"] == limites.CERCA


def test_alerta_limite_superado(con_alumnos):
    """Con más faltas que el límite, el estado es superado."""
    limites.cambiar_configuracion(con_alumnos, "2", "0")
    faltar(con_alumnos, JUAN, 3)
    resultado = situacion(con_alumnos)
    assert resultado["estado"] == limites.SUPERADO
    assert "tiene 3 y el máximo es 2" in resultado["mensaje"]


def test_limite_del_curso_cambia_la_alerta(con_alumnos):
    """El mismo alumno puede pasar a alerta si su curso es más
    exigente."""
    faltar(con_alumnos, JUAN, 3)
    assert situacion(con_alumnos)["estado"] == limites.NORMAL
    curso = cursos.obtener(con_alumnos, CURSO_ID)
    cursos.modificar(con_alumnos, curso.id, curso.nombre, curso.anio,
                     curso.division, curso.docente_id, "3")
    assert situacion(con_alumnos)["estado"] == limites.CERCA


def test_alumnos_con_alerta_ordenados(con_alumnos):
    """Primero los que superaron el límite, después los que están
    cerca."""
    limites.cambiar_configuracion(con_alumnos, "4", "0")
    faltar(con_alumnos, JUAN, 3)                 # cerca (75 %)
    faltar(con_alumnos, "1234567", 5)            # superado
    alta_alumno(con_alumnos, "40111222", "Zoe", "Álvarez")   # sin faltas
    alertas = limites.alumnos_con_alerta(con_alumnos)
    assert [(a["nombre"], a["estado"]) for a in alertas] == [
        ("Ana Gómez", limites.SUPERADO), ("Juan Pérez", limites.CERCA)]


def test_situacion_de_todos_coincide_con_la_individual(con_alumnos):
    """El cálculo para el listado da lo mismo que el del informe."""
    limites.cambiar_configuracion(con_alumnos, "5", "0.25")
    faltar(con_alumnos, JUAN, 2)
    llegar_tarde(con_alumnos, JUAN, 2)
    todos = limites.situacion_de_todos(con_alumnos)
    juan = informes.informe_alumno(con_alumnos, JUAN)
    alumno_id = [k for k, v in todos.items()
                 if v["faltas_texto"] == "2.5"][0]
    assert todos[alumno_id] == juan["situacion"]


# ----------------------------------------------------------------------
# Pantallas
# ----------------------------------------------------------------------

@pytest.fixture
def con_juan_en_alerta(cliente, ruta_memoria):
    """Cliente admin con Juan cerca del límite (3 de 4 faltas)."""
    cliente.post("/alumnos", data=datos_alumno(JUAN, "Juan", "Pérez"))
    with closing(bd.conectar(ruta_memoria)) as conexion:
        limites.cambiar_configuracion(conexion, "4", "0")
        faltar(conexion, JUAN, 3)
    return cliente


def test_pantalla_de_limites(cliente):
    """La pantalla muestra y guarda la configuración."""
    r = cliente.get("/limites")
    assert r.status_code == 200 and 'value="10"' in r.text
    r = cliente.post("/limites", data={"limite_faltas": "12",
                                       "valor_tardanza": "0.5"},
                     follow_redirects=True)
    assert "Límite general: 12 faltas. 2 tardanzas = 1 falta." in r.text


def test_pantalla_de_limites_con_error(cliente):
    """Un límite inválido se explica en la pantalla."""
    r = cliente.post("/limites", data={"limite_faltas": "0",
                                       "valor_tardanza": "0"})
    assert r.status_code == 400 and "entre 1 y 365" in r.text


def test_informe_muestra_alerta_cerca(con_juan_en_alerta):
    """El informe del alumno avisa que está cerca del límite."""
    r = con_juan_en_alerta.get(f"/informe?dni={JUAN}")
    assert "Atención." in r.text and "3 de 4 faltas (75 %)" in r.text
    assert "Le quedan 1" in r.text


def test_informe_muestra_limite_superado(con_juan_en_alerta, ruta_memoria):
    """Si superó el límite, el informe lo dice."""
    with closing(bd.conectar(ruta_memoria)) as conexion:
        faltar(conexion, JUAN, 2, desde=4)
    r = con_juan_en_alerta.get(f"/informe?dni={JUAN}")
    assert "Límite superado." in r.text


def test_dashboard_lista_alertas(con_juan_en_alerta):
    """El dashboard muestra los alumnos con alerta."""
    r = con_juan_en_alerta.get("/")
    assert 'id="alertas-faltas"' in r.text
    assert "Cerca · 3/4" in r.text


def test_listado_de_alumnos_muestra_faltas(con_juan_en_alerta):
    """El listado de alumnos muestra faltas / límite con color."""
    r = con_juan_en_alerta.get("/alumnos")
    assert "badge-cerca" in r.text and "3 / 4" in r.text


def test_curso_con_limite_propio_desde_la_pantalla(cliente):
    """El límite del curso se carga desde el formulario de cursos."""
    r = cliente.post("/cursos/1", data={"nombre": "Programación",
                                        "anio": "3", "division": "A",
                                        "docente_id": "1",
                                        "limite_faltas": "6"},
                     follow_redirects=True)
    assert "<td>6</td>" in r.text


def test_alumno_ve_su_alerta(cliente_alumno, ruta_memoria):
    """En Mi asistencia el alumno también ve la alerta."""
    with closing(bd.conectar(ruta_memoria)) as conexion:
        limites.cambiar_configuracion(conexion, "2", "0")
        faltar(conexion, JUAN, 3)
    r = cliente_alumno.get("/mi-asistencia")
    assert "Límite superado." in r.text


def test_docente_ve_limites_pero_no_los_cambia(cliente_docente):
    """El docente consulta la configuración; no puede guardarla."""
    r = cliente_docente.get("/limites")
    assert r.status_code == 200 and "Solo un administrador" in r.text
    r = cliente_docente.post("/limites", data={"limite_faltas": "3",
                                               "valor_tardanza": "1"})
    assert r.status_code == 403


def test_alumno_no_entra_a_limites(cliente_alumno):
    """La configuración no es para alumnos."""
    assert cliente_alumno.get("/limites").status_code == 403
