"""Tests de servicios/informes.py: informe por alumno y dashboard."""
from datetime import date

import pytest

from asistencia.servicios import alumnos, asistencias, informes
from asistencia.validaciones import ErrorValidacion
from tests.conftest import HOY, a_las


def test_informe_con_porcentajes(con_alumnos):
    """Tardanzas cuentan como asistencia; el detalle va del más
    reciente al más viejo."""
    conexion = con_alumnos
    asistencias.registrar(conexion, "45123456",
                          ahora=a_las(8, 0, date(2026, 11, 2)))   # presente
    asistencias.registrar(conexion, "45123456",
                          ahora=a_las(8, 30, date(2026, 11, 3)))  # tardanza
    asistencias.carga_manual(conexion, "45123456", "2026-11-04",
                             "AUSENTE", "", hoy=HOY)              # ausente
    asistencias.registrar(conexion, "45123456",
                          ahora=a_las(8, 10, date(2026, 11, 5)))  # presente

    informe = informes.informe_alumno(conexion, "45123456")
    assert (informe["presentes"], informe["tardanzas"],
            informe["ausentes"]) == (2, 1, 1)
    assert informe["total"] == 4
    assert informe["porcentaje_asistencia"] == 75.0
    assert informe["porcentaje_ausentes"] == 25.0
    assert informe["detalle"][0]["fecha"] == "2026-11-05"
    assert informe["detalle"][0]["fecha_mostrar"] == "05/11/2026"


def test_informe_sin_registros_no_divide_por_cero(con_alumnos):
    """Un alumno sin registros tiene 0 %, sin errores."""
    informe = informes.informe_alumno(con_alumnos, "1234567")
    assert informe["total"] == 0
    assert informe["porcentaje_asistencia"] == 0.0


def test_informe_dni_inexistente(con_alumnos):
    """El informe de un DNI que no existe da error de validación."""
    with pytest.raises(ErrorValidacion):
        informes.informe_alumno(con_alumnos, "11111111")


def test_porcentajes_por_alumno(con_alumnos):
    """Calcula el % de cada alumno con registros."""
    asistencias.registrar(con_alumnos, "45123456", ahora=a_las(8, 0))
    asistencias.cerrar_dia(con_alumnos, hoy=HOY)
    juan = alumnos.buscar_por_dni(con_alumnos, "45123456")
    ana = alumnos.buscar_por_dni(con_alumnos, "1234567")
    porcentajes = informes.porcentajes_por_alumno(con_alumnos)
    assert porcentajes == {juan.id: 100.0, ana.id: 0.0}


def test_resumen_general_vacio(conexion):
    """Sin registros, el dashboard no falla y muestra todo en cero."""
    resumen = informes.resumen_general(conexion, HOY)
    assert resumen["alumnos"] == 0
    assert resumen["dias"] == [] and resumen["maximo_dia"] == 0
    assert resumen["porcentaje_asistencia"] == 0.0


def test_resumen_general_con_datos(con_alumnos):
    """Gráfico de días, porcentaje general y ranking de ausencias."""
    conexion = con_alumnos
    ayer = date(2026, 11, 5)
    asistencias.registrar(conexion, "45123456", ahora=a_las(8, 0, ayer))
    asistencias.cerrar_dia(conexion, hoy=ayer)          # Ana ausente
    asistencias.registrar(conexion, "45123456", ahora=a_las(8, 30))
    asistencias.registrar(conexion, "1234567", ahora=a_las(8, 0))

    resumen = informes.resumen_general(conexion, HOY)
    fechas = [d["fecha"] for d in resumen["dias"]]
    assert fechas == ["2026-11-05", "2026-11-06"]
    assert resumen["dias"][1]["etiqueta"] == "Vie 06/11"
    assert resumen["maximo_dia"] == 2
    assert resumen["porcentaje_asistencia"] == 75.0
    assert resumen["mas_ausencias"] == [
        {"dni": "1234567", "nombre": "Ana Gómez", "cantidad": 1}]
    assert resumen["mas_tardanzas"][0]["nombre"] == "Juan Pérez"


def test_resumen_general_no_incluye_dias_futuros(con_alumnos):
    """El gráfico llega solo hasta el día de hoy."""
    asistencias.registrar(con_alumnos, "45123456",
                          ahora=a_las(8, 0, date(2026, 11, 10)))
    resumen = informes.resumen_general(con_alumnos, HOY)
    assert resumen["dias"] == []
