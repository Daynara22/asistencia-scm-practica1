"""Tests de servicios/informes.py: informe por alumno y dashboard."""
from datetime import date

import pytest

from asistencia.servicios import alumnos, asistencias, informes, limites
from asistencia.validaciones import ErrorValidacion
from tests.conftest import HOY, a_las, alta_alumno, crear_curso


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


# ----------------------------------------------------------------------
# Filtro por fechas
# ----------------------------------------------------------------------

@pytest.fixture
def con_semana(con_alumnos):
    """Juan: presente el 2, tarde el 3 y ausente el 4 de noviembre.
    Ana: ausente el 4."""
    asistencias.registrar(con_alumnos, "45123456",
                          ahora=a_las(8, 0, date(2026, 11, 2)))
    asistencias.registrar(con_alumnos, "45123456",
                          ahora=a_las(8, 30, date(2026, 11, 3)))
    asistencias.cerrar_dia(con_alumnos, hoy=date(2026, 11, 4))
    return con_alumnos


@pytest.mark.parametrize("desde, hasta", [
    ("", ""), ("2026-11-01", ""), ("", "2026-11-30"),
    ("2026-11-01", "2026-11-01")])
def test_validar_rango_correcto(desde, hasta):
    """Las fechas pueden faltar; si están, se convierten en date."""
    inicio, fin = informes.validar_rango(desde, hasta)
    assert inicio == (date(2026, 11, 1) if desde else None)
    assert fin == (date.fromisoformat(hasta) if hasta else None)


@pytest.mark.parametrize("desde, hasta, mensaje", [
    ("2026-11-10", "2026-11-01", "posterior"),
    ("2026-02-30", "", "no existe"),
    ("06/11/2026", "", "formato"),
])
def test_validar_rango_incorrecto(desde, hasta, mensaje):
    """Fechas inválidas o en orden inverso dan error claro."""
    with pytest.raises(ErrorValidacion, match=mensaje):
        informes.validar_rango(desde, hasta)


def test_informe_alumno_filtrado(con_semana):
    """Solo cuenta los registros dentro del período."""
    informe = informes.informe_alumno(con_semana, "45123456",
                                      date(2026, 11, 3), date(2026, 11, 4))
    assert (informe["presentes"], informe["tardanzas"],
            informe["ausentes"]) == (0, 1, 1)
    assert informe["periodo"] == "Del 03/11/2026 al 04/11/2026"
    assert informe["filtrado"] is True
    assert informe["curso"] == "Programación 3° A"


def test_filtro_no_cambia_la_situacion_del_limite(con_semana):
    """El estado respecto del límite cuenta todo el ciclo."""
    completo = informes.informe_alumno(con_semana, "45123456")
    filtrado = informes.informe_alumno(con_semana, "45123456",
                                       date(2026, 11, 2), date(2026, 11, 2))
    assert filtrado["ausentes"] == 0
    assert filtrado["situacion"] == completo["situacion"]


# ----------------------------------------------------------------------
# Informe total
# ----------------------------------------------------------------------

def test_informe_total_general_y_por_curso(con_semana):
    """Suma todos los alumnos y separa por curso."""
    otro = crear_curso(con_semana, nombre="Arte", division="B")
    alta_alumno(con_semana, "40111222", "Zoe", "Álvarez", otro.id)

    total = informes.informe_total(con_semana)

    general = total["general"]
    assert (general["alumnos"], general["presentes"], general["tardanzas"],
            general["ausentes"]) == (3, 1, 1, 2)
    assert general["porcentaje_asistencia"] == 50.0
    por_curso = {c["nombre"]: c for c in total["cursos"]}
    assert por_curso["Programación 3° A"]["alumnos"] == 2
    assert por_curso["Arte 3° B"]["total"] == 0   # Zoe sin registros
    assert total["periodo"] == "Todo el período"


def test_informe_total_filtrado_por_fecha(con_semana):
    """Con fechas, solo cuenta ese período (y muestra a todos los
    alumnos)."""
    total = informes.informe_total(con_semana, date(2026, 11, 4),
                                   date(2026, 11, 4))
    assert total["general"]["ausentes"] == 2
    assert total["general"]["presentes"] == 0
    assert len(total["alumnos"]) == 2


def test_informe_total_filtrado_por_curso(con_semana):
    """Con curso, solo sus alumnos."""
    otro = crear_curso(con_semana, nombre="Arte", division="B")
    alta_alumno(con_semana, "40111222", "Zoe", "Álvarez", otro.id)
    total = informes.informe_total(con_semana, curso_id=otro.id)
    assert [a["nombre"] for a in total["alumnos"]] == ["Zoe Álvarez"]
    assert total["curso"] == "Arte 3° B"


def test_informe_total_curso_inexistente(con_semana):
    """Filtrar por un curso que no existe da error."""
    with pytest.raises(ErrorValidacion, match="no existe"):
        informes.informe_total(con_semana, curso_id="99")


def test_informe_total_cuenta_alertas(con_semana):
    """Cuenta cuántos alumnos están cerca del límite o lo superaron."""
    limites.cambiar_configuracion(con_semana, "1", "0")
    total = informes.informe_total(con_semana)
    # Juan y Ana tienen 1 ausencia de 1 permitida: están en el límite.
    assert total["general"]["cerca"] == 2
    assert total["general"]["superados"] == 0


def test_informe_total_alumnos_sin_curso(con_semana):
    """Los alumnos sin curso aparecen en el grupo "Sin curso", al
    final."""
    juan = alumnos.buscar_por_dni(con_semana, "45123456")
    alumnos.modificar(con_semana, juan.id, juan.dni, juan.nombre,
                      juan.apellido, "", "")
    total = informes.informe_total(con_semana)
    assert total["cursos"][-1]["nombre"] == "Sin curso"
    assert total["alumnos"][-1]["nombre"] == "Juan Pérez"


def test_texto_del_periodo_solo_hasta(con_semana):
    """Con solo la fecha final, el período lo dice así."""
    informe = informes.informe_alumno(con_semana, "45123456",
                                      hasta=date(2026, 11, 3))
    assert informe["periodo"] == "Hasta el 03/11/2026"
    assert informe["total"] == 2
