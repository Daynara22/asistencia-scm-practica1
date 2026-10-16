import pytest

import main


@pytest.fixture(autouse=True)
def limpiar_estado():
    # Se modifica el estado a través del módulo (main.x) y no con
    # "from main import ...": total_asistencias es un int, así que importarlo
    # copiaría el valor y el reinicio no afectaría a la variable real de main.
    main.total_asistencias = 0
    main.historial_registros.clear()


def test_registrar_asistencia_exitoso():
    """Un DNI válido registra la asistencia y queda guardada en el historial."""
    resultado = main.registrar_asistencia({"dni": "40123456", "materia": "Programación III"})

    assert resultado is True
    assert main.total_asistencias == 1
    assert len(main.historial_registros) == 1
    assert main.historial_registros[0]["dni"] == "40123456"
    assert main.historial_registros[0]["materia"] == "Programación III"


def test_registrar_asistencia_materia_personalizada():
    """La materia indicada en los datos del alumno se guarda en el registro."""
    resultado = main.registrar_asistencia({"dni": "38999111", "materia": "Práctica Profesional II"})

    assert resultado is True
    assert main.historial_registros[0]["materia"] == "Práctica Profesional II"


def test_registrar_asistencia_dni_invalido_corto():
    """Un DNI con menos de 7 dígitos se rechaza y no modifica el estado."""
    resultado = main.registrar_asistencia({"dni": "123", "materia": "Programación III"})

    assert resultado is False
    assert main.total_asistencias == 0
    assert main.historial_registros == []


def test_registrar_asistencia_dni_con_letras():
    """Un DNI que contiene letras se rechaza y no suma asistencias."""
    resultado = main.registrar_asistencia({"dni": "40123ABC", "materia": "Programación III"})

    assert resultado is False
    assert main.total_asistencias == 0


def test_registrar_asistencia_sin_dni():
    """Si falta el campo DNI, la asistencia se rechaza y no suma."""
    resultado = main.registrar_asistencia({"materia": "Programación III"})

    assert resultado is False
    assert main.total_asistencias == 0


def test_obtener_reporte_estadistico():
    """El reporte devuelve el total y el detalle de los registros en orden."""
    main.registrar_asistencia({"dni": "40123456", "materia": "Programación III"})
    main.registrar_asistencia({"dni": "41222333", "materia": "Práctica Profesional II"})

    reporte = main.obtener_reporte_estadistico()

    assert reporte["total_asistencias"] == 2
    assert len(reporte["detalle"]) == 2
    assert reporte["detalle"][0]["dni"] == "40123456"
    assert reporte["detalle"][1]["dni"] == "41222333"
