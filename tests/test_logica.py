"""Tests de las reglas y validaciones (logica.py) y del guardado en JSON (datos.py)."""
import json
from datetime import date, datetime

import pytest

import datos as almacen
import logica
from logica import ErrorValidacion

HOY = date(2026, 11, 6)


@pytest.fixture
def datos():
    """Datos de prueba con dos alumnos y hora límite 08:15."""
    d = almacen.datos_vacios()
    logica.alta_alumno(d, "45123456", "juan", "pérez")
    logica.alta_alumno(d, "1234567", "Ana", "Gómez")
    return d


def a_las(hora, minuto, dia=HOY):
    return datetime(dia.year, dia.month, dia.day, hora, minuto)


# ---------------- Validación de DNI ----------------

@pytest.mark.parametrize("dni", ["45123456", "1234567", " 45123456 ", "45.123.456"])
def test_dni_valido(dni):
    assert logica.validar_dni(dni) in ("45123456", "1234567")


@pytest.mark.parametrize("dni", ["", "   ", None, "abc12345", "4512345a", "123456", "123456789", "-1234567", "12345.6.7.8.9"])
def test_dni_invalido(dni):
    with pytest.raises(ErrorValidacion):
        logica.validar_dni(dni)


# ---------------- Alta de alumnos ----------------

def test_alta_normaliza_nombre(datos):
    assert datos["alumnos"]["45123456"] == {"nombre": "Juan", "apellido": "Pérez"}


@pytest.mark.parametrize("nombre, apellido", [("", "Pérez"), ("Juan", "   "), ("Juan2", "Pérez"), ("Juan", "P@rez")])
def test_alta_con_nombre_invalido(nombre, apellido):
    d = almacen.datos_vacios()
    with pytest.raises(ErrorValidacion):
        logica.alta_alumno(d, "40111222", nombre, apellido)
    assert d["alumnos"] == {}


def test_no_permite_dni_duplicado(datos):
    with pytest.raises(ErrorValidacion, match="Ya existe"):
        logica.alta_alumno(datos, "45.123.456", "Otro", "Alumno")


def test_acepta_nombres_compuestos():
    d = almacen.datos_vacios()
    logica.alta_alumno(d, "40111222", "maría  josé", "o'brien-núñez")
    assert d["alumnos"]["40111222"] == {"nombre": "María José", "apellido": "O'Brien-Núñez"}


# ---------------- Fechas y horas ----------------

@pytest.mark.parametrize("texto", ["2026-02-30", "2026-13-01", "2026-2-3", "06/11/2026", "", "hoy"])
def test_fecha_invalida(texto):
    with pytest.raises(ErrorValidacion):
        logica.validar_fecha(texto)


@pytest.mark.parametrize("texto", ["25:00", "08:60", "8:15", "0815", "", "ocho"])
def test_hora_invalida(texto):
    with pytest.raises(ErrorValidacion):
        logica.validar_hora(texto)


def test_horas_se_comparan_como_horas():
    limite = logica.validar_hora("09:30")
    # Como texto, "10:05" < "9:30" sería True; como hora, 10:05 es más tarde.
    assert logica.calcular_estado(logica.validar_hora("10:05"), limite) == logica.TARDANZA
    assert logica.calcular_estado(logica.validar_hora("09:30"), limite) == logica.PRESENTE


# ---------------- Registro de asistencia ----------------

def test_presente_hasta_la_hora_limite_inclusive(datos):
    resultado = logica.registrar_asistencia(datos, "45123456", ahora=a_las(8, 15))
    assert resultado["estado"] == logica.PRESENTE
    assert resultado["nombre"] == "Juan Pérez"


def test_tardanza_despues_de_la_hora_limite(datos):
    resultado = logica.registrar_asistencia(datos, "45123456", ahora=a_las(8, 16))
    assert resultado["estado"] == logica.TARDANZA
    assert resultado["hora"] == "08:16"


def test_respeta_hora_limite_cambiada(datos):
    logica.cambiar_hora_limite(datos, "07:30")
    assert logica.registrar_asistencia(datos, "45123456", ahora=a_las(7, 45))["estado"] == logica.TARDANZA


def test_cambiar_hora_limite_invalida(datos):
    with pytest.raises(ErrorValidacion):
        logica.cambiar_hora_limite(datos, "99:99")
    assert datos["config"]["hora_limite"] == "08:15"


def test_un_solo_registro_por_dia(datos):
    logica.registrar_asistencia(datos, "45123456", ahora=a_las(8, 0))
    with pytest.raises(ErrorValidacion, match="ya tiene registrada"):
        logica.registrar_asistencia(datos, "45123456", ahora=a_las(8, 5))


def test_otro_dia_si_puede_registrar(datos):
    logica.registrar_asistencia(datos, "45123456", ahora=a_las(8, 0))
    logica.registrar_asistencia(datos, "45123456", ahora=a_las(8, 0, date(2026, 11, 9)))
    assert len(datos["asistencias"]) == 2


def test_registrar_dni_inexistente(datos):
    with pytest.raises(ErrorValidacion, match="No hay ningún alumno"):
        logica.registrar_asistencia(datos, "99999999", ahora=a_las(8, 0))


# ---------------- Cierre del día ----------------

def test_cerrar_dia_marca_ausentes(datos):
    logica.registrar_asistencia(datos, "45123456", ahora=a_las(8, 0))
    marcados = logica.cerrar_dia(datos, hoy=HOY)
    assert marcados == 1
    assert datos["asistencias"]["2026-11-06"]["1234567"]["estado"] == logica.AUSENTE
    assert datos["asistencias"]["2026-11-06"]["45123456"]["estado"] == logica.PRESENTE


def test_no_registra_con_dia_cerrado(datos):
    logica.cerrar_dia(datos, hoy=HOY)
    with pytest.raises(ErrorValidacion, match="cerrado"):
        logica.registrar_asistencia(datos, "45123456", ahora=a_las(9, 0))


def test_no_cierra_dos_veces(datos):
    logica.cerrar_dia(datos, hoy=HOY)
    with pytest.raises(ErrorValidacion):
        logica.cerrar_dia(datos, hoy=HOY)


# ---------------- Carga manual ----------------

def test_carga_manual_tardanza(datos):
    r = logica.carga_manual(datos, "45123456", "2026-11-02", "tardanza", "08:40", hoy=HOY)
    assert r["estado"] == logica.TARDANZA and r["hora"] == "08:40" and r["manual"] is True


def test_carga_manual_ausente_sin_hora(datos):
    r = logica.carga_manual(datos, "45123456", "2026-11-02", "AUSENTE", "", hoy=HOY)
    assert r["estado"] == logica.AUSENTE and r["hora"] is None


def test_carga_manual_tardanza_pide_hora(datos):
    with pytest.raises(ErrorValidacion, match="hora de llegada"):
        logica.carga_manual(datos, "45123456", "2026-11-02", "TARDANZA", "", hoy=HOY)


def test_carga_manual_tardanza_antes_del_limite(datos):
    with pytest.raises(ErrorValidacion, match="no es tardanza"):
        logica.carga_manual(datos, "45123456", "2026-11-02", "TARDANZA", "08:00", hoy=HOY)


def test_carga_manual_fecha_futura(datos):
    with pytest.raises(ErrorValidacion, match="futura"):
        logica.carga_manual(datos, "45123456", "2026-11-07", "AUSENTE", "", hoy=HOY)


def test_carga_manual_estado_invalido(datos):
    with pytest.raises(ErrorValidacion):
        logica.carga_manual(datos, "45123456", "2026-11-02", "PRESENTE", "08:00", hoy=HOY)


def test_carga_manual_duplicada(datos):
    logica.carga_manual(datos, "45123456", "2026-11-02", "AUSENTE", "", hoy=HOY)
    with pytest.raises(ErrorValidacion, match="ya tiene un registro"):
        logica.carga_manual(datos, "45123456", "2026-11-02", "TARDANZA", "09:00", hoy=HOY)


# ---------------- Informe ----------------

def test_informe_con_porcentajes(datos):
    logica.registrar_asistencia(datos, "45123456", ahora=a_las(8, 0, date(2026, 11, 2)))   # presente
    logica.registrar_asistencia(datos, "45123456", ahora=a_las(8, 30, date(2026, 11, 3)))  # tardanza
    logica.carga_manual(datos, "45123456", "2026-11-04", "AUSENTE", "", hoy=HOY)           # ausente
    logica.registrar_asistencia(datos, "45123456", ahora=a_las(8, 10, date(2026, 11, 5)))  # presente

    informe = logica.informe_alumno(datos, "45123456")
    assert (informe["presentes"], informe["tardanzas"], informe["ausentes"]) == (2, 1, 1)
    assert informe["total"] == 4
    assert informe["porcentaje_asistencia"] == 75.0
    assert informe["detalle"][0]["fecha"] == "2026-11-05"   # el más reciente primero


def test_informe_sin_registros_no_divide_por_cero(datos):
    informe = logica.informe_alumno(datos, "1234567")
    assert informe["total"] == 0 and informe["porcentaje_asistencia"] == 0.0


def test_informe_dni_inexistente(datos):
    with pytest.raises(ErrorValidacion):
        logica.informe_alumno(datos, "11111111")


# ---------------- Archivo JSON ----------------

def test_guardar_y_cargar(tmp_path, datos):
    archivo = tmp_path / "datos" / "asistencia.json"
    almacen.guardar(datos, str(archivo))
    cargados, aviso = almacen.cargar(str(archivo))
    assert aviso is None
    assert cargados == datos
    assert "Pérez" in archivo.read_text(encoding="utf-8")   # tildes guardadas legibles


def test_archivo_inexistente_empieza_vacio(tmp_path):
    cargados, aviso = almacen.cargar(str(tmp_path / "no_existe.json"))
    assert aviso is None and cargados == almacen.datos_vacios()


@pytest.mark.parametrize("contenido", ["{esto no es json", "[]", '{"alumnos": 5}', ""])
def test_json_danado_hace_copia_y_sigue(tmp_path, contenido):
    archivo = tmp_path / "asistencia.json"
    archivo.write_text(contenido, encoding="utf-8")

    cargados, aviso = almacen.cargar(str(archivo))

    assert cargados == almacen.datos_vacios()
    assert "dañado" in aviso
    copias = list(tmp_path.glob("asistencia.danado-*.json"))
    assert len(copias) == 1 and copias[0].read_text(encoding="utf-8") == contenido
    assert json.loads(archivo.read_text(encoding="utf-8")) == almacen.datos_vacios()


# ----------------------------------------------------------------------
# Contraseñas de docentes
# ----------------------------------------------------------------------

def test_hash_de_clave_se_verifica():
    hash_guardado = logica.generar_hash_clave("Clave123!")
    assert hash_guardado.startswith("scrypt:") and "Clave123!" not in hash_guardado
    assert logica.verificar_clave(hash_guardado, "Clave123!")
    assert not logica.verificar_clave(hash_guardado, "Clave1234!")


def test_hash_de_clave_usa_sal_distinta():
    assert logica.generar_hash_clave("Clave123!") != logica.generar_hash_clave("Clave123!")


def test_hash_danado_no_rompe():
    assert not logica.verificar_clave("cualquier-cosa", "Clave123!")
    assert not logica.verificar_clave("md5$sal$abc", "Clave123!")
