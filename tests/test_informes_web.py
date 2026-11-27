"""Tests de las pantallas de informes: por alumno, total y Mi
asistencia."""
from contextlib import closing
from datetime import date

import pytest

from asistencia import bd
from asistencia.servicios import asistencias
from tests.conftest import a_las, datos_alumno

JUAN = "45123456"


@pytest.fixture
def con_datos(cliente, ruta_memoria):
    """Juan presente el 2/11 y ausente el 4/11; Ana sin registros."""
    cliente.post("/alumnos", data=datos_alumno(JUAN, "Juan", "Pérez"))
    cliente.post("/alumnos", data=datos_alumno("40111222", "Ana", "Díaz"))
    with closing(bd.conectar(ruta_memoria)) as conexion:
        asistencias.registrar(conexion, JUAN,
                              ahora=a_las(8, 0, date(2026, 11, 2)))
        asistencias.carga_manual(conexion, JUAN, "2026-11-04", "AUSENTE",
                                 "", hoy=date(2026, 11, 6))
    return cliente


def test_menu_lleva_a_informes(cliente):
    """El menú tiene el enlace al panel de informes."""
    assert 'href="/informes"' in cliente.get("/").text


def test_informe_total_sin_filtros(con_datos):
    """Muestra el resumen general, por curso y por alumno."""
    r = con_datos.get("/informes")
    assert r.status_code == 200
    assert "Todo el período" in r.text
    assert 'id="tabla-cursos"' in r.text
    assert "Programación 3° A" in r.text
    assert "Juan Pérez" in r.text and "Ana Díaz" in r.text
    assert "50.0 %" in r.text                       # 1 de 2 registros
    assert 'class="barra-asistencia"' in r.text     # gráfico


def test_informe_total_filtrado(con_datos):
    """Con fechas, cambia el período y las cantidades."""
    r = con_datos.get("/informes?desde=2026-11-04&hasta=2026-11-04")
    assert "Del 04/11/2026 al 04/11/2026" in r.text
    assert "0.0 %" in r.text


def test_informe_total_enlaces_de_descarga_con_filtros(con_datos):
    """Los botones de descarga conservan los filtros elegidos."""
    r = con_datos.get("/informes?desde=2026-11-01&curso=1")
    assert 'href="/informes/csv?desde=2026-11-01&amp;curso=1"' in r.text
    assert 'href="/informes/pdf?desde=2026-11-01&amp;curso=1"' in r.text


@pytest.mark.parametrize("consulta, mensaje", [
    ("desde=2026-11-10&hasta=2026-11-01", "posterior"),
    ("desde=2026-13-01", "no existe"),
    ("desde=01/11/2026", "formato"),
    ("curso=99", "no existe"),
])
def test_informe_total_filtros_invalidos(con_datos, consulta, mensaje):
    """Filtros inválidos se explican sin romper la pantalla."""
    r = con_datos.get(f"/informes?{consulta}")
    assert r.status_code == 400 and mensaje in r.text


def test_informe_por_alumno_con_fechas(con_datos):
    """El informe por alumno respeta el filtro y lo aclara."""
    r = con_datos.get(f"/informe?dni={JUAN}&desde=2026-11-03")
    assert "Desde el 03/11/2026" in r.text
    assert "las faltas y el límite cuentan todo el ciclo" in r.text
    assert f'href="/informe/pdf?dni={JUAN}&amp;desde=2026-11-03"' in r.text


def test_informe_por_alumno_sin_registros_en_el_periodo(con_datos):
    """Si no hay registros en el período, se avisa."""
    r = con_datos.get(f"/informe?dni={JUAN}&desde=2026-12-01")
    assert "No hay asistencias registradas en el período elegido" in r.text


def test_mi_asistencia_con_filtro(cliente_alumno, ruta_memoria):
    """El alumno filtra su informe por fechas y puede descargarlo."""
    with closing(bd.conectar(ruta_memoria)) as conexion:
        asistencias.registrar(conexion, JUAN,
                              ahora=a_las(8, 0, date(2026, 11, 2)))
    r = cliente_alumno.get("/mi-asistencia?desde=2026-11-01")
    assert r.status_code == 200 and "Desde el 01/11/2026" in r.text
    assert 'name="dni"' not in r.text
    assert 'href="/mi-asistencia/pdf?desde=2026-11-01"' in r.text


def test_docente_ve_los_informes(cliente_docente):
    """Los docentes también usan el panel de informes."""
    assert cliente_docente.get("/informes").status_code == 200


def test_alumno_no_ve_el_informe_total(cliente_alumno):
    """El informe total no es para alumnos."""
    assert cliente_alumno.get("/informes").status_code == 403
