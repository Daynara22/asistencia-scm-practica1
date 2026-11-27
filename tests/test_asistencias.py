"""Tests de servicios/asistencias.py y de la hora límite."""
from datetime import date

import pytest

from asistencia.modelos import AUSENTE, PRESENTE, TARDANZA
from asistencia.servicios import asistencias, configuracion
from asistencia.validaciones import ErrorValidacion, validar_hora
from tests.conftest import HOY, a_las


def estado_de(conexion, dni, fecha):
    """Estado guardado de un alumno en una fecha (o None)."""
    fila = conexion.execute(
        "SELECT a.estado FROM asistencias a JOIN alumnos al "
        "ON al.id = a.alumno_id WHERE al.dni = ? AND a.fecha = ?",
        (dni, fecha.isoformat())).fetchone()
    return fila["estado"] if fila else None


def test_horas_se_comparan_como_horas():
    """Como texto "10:05" < "9:30"; como hora, 10:05 es más tarde."""
    limite = validar_hora("09:30")
    assert asistencias.calcular_estado(validar_hora("10:05"), limite) == \
        TARDANZA
    assert asistencias.calcular_estado(validar_hora("09:30"), limite) == \
        PRESENTE


# ---------------- Hora límite ----------------

def test_hora_limite_por_defecto(conexion):
    """Una base nueva empieza con la hora límite 08:15."""
    assert configuracion.texto_hora_limite(conexion) == "08:15"


def test_cambiar_hora_limite_invalida(conexion):
    """Una hora inválida no cambia la configuración."""
    with pytest.raises(ErrorValidacion):
        configuracion.cambiar_hora_limite(conexion, "99:99")
    assert configuracion.texto_hora_limite(conexion) == "08:15"


# ---------------- Registro ----------------

def test_presente_hasta_la_hora_limite_inclusive(con_alumnos):
    """Llegar justo a la hora límite cuenta como PRESENTE."""
    resultado = asistencias.registrar(con_alumnos, "45123456",
                                      ahora=a_las(8, 15))
    assert resultado["estado"] == PRESENTE
    assert resultado["nombre"] == "Juan Pérez"
    assert estado_de(con_alumnos, "45123456", HOY) == PRESENTE


def test_tardanza_despues_de_la_hora_limite(con_alumnos):
    """Un minuto después de la hora límite es TARDANZA."""
    resultado = asistencias.registrar(con_alumnos, "45123456",
                                      ahora=a_las(8, 16))
    assert resultado["estado"] == TARDANZA
    assert resultado["hora"] == "08:16"


def test_respeta_hora_limite_cambiada(con_alumnos):
    """El estado se calcula con la hora límite guardada."""
    configuracion.cambiar_hora_limite(con_alumnos, "07:30")
    resultado = asistencias.registrar(con_alumnos, "45123456",
                                      ahora=a_las(7, 45))
    assert resultado["estado"] == TARDANZA


def test_un_solo_registro_por_dia(con_alumnos):
    """No se puede registrar dos veces el mismo día."""
    asistencias.registrar(con_alumnos, "45123456", ahora=a_las(8, 0))
    with pytest.raises(ErrorValidacion, match="ya tiene registrada"):
        asistencias.registrar(con_alumnos, "45123456", ahora=a_las(8, 5))


def test_otro_dia_si_puede_registrar(con_alumnos):
    """Al día siguiente el alumno se puede registrar de nuevo."""
    asistencias.registrar(con_alumnos, "45123456", ahora=a_las(8, 0))
    asistencias.registrar(con_alumnos, "45123456",
                          ahora=a_las(8, 0, date(2026, 11, 9)))
    total = con_alumnos.execute(
        "SELECT COUNT(*) FROM asistencias").fetchone()[0]
    assert total == 2


def test_registrar_dni_inexistente(con_alumnos):
    """Registrar un DNI que no existe da un mensaje claro."""
    with pytest.raises(ErrorValidacion, match="No hay ningún alumno"):
        asistencias.registrar(con_alumnos, "99999999", ahora=a_las(8, 0))


# ---------------- Cierre del día ----------------

def test_cerrar_dia_marca_ausentes(con_alumnos):
    """Quien no se registró queda AUSENTE; los demás no cambian."""
    asistencias.registrar(con_alumnos, "45123456", ahora=a_las(8, 0))
    marcados = asistencias.cerrar_dia(con_alumnos, hoy=HOY)
    assert marcados == 1
    assert estado_de(con_alumnos, "1234567", HOY) == AUSENTE
    assert estado_de(con_alumnos, "45123456", HOY) == PRESENTE
    assert asistencias.dia_cerrado(con_alumnos, HOY)


def test_no_registra_con_dia_cerrado(con_alumnos):
    """Con el día cerrado no se aceptan más registros."""
    asistencias.cerrar_dia(con_alumnos, hoy=HOY)
    with pytest.raises(ErrorValidacion, match="cerrado"):
        asistencias.registrar(con_alumnos, "45123456", ahora=a_las(9, 0))


def test_no_cierra_dos_veces(con_alumnos):
    """Un día ya cerrado no se puede volver a cerrar."""
    asistencias.cerrar_dia(con_alumnos, hoy=HOY)
    with pytest.raises(ErrorValidacion):
        asistencias.cerrar_dia(con_alumnos, hoy=HOY)


# ---------------- Carga manual ----------------

def test_carga_manual_tardanza(con_alumnos):
    """Se carga una tardanza de otro día con su hora de llegada."""
    r = asistencias.carga_manual(con_alumnos, "45123456", "2026-11-02",
                                 "tardanza", "08:40", hoy=HOY)
    assert r["estado"] == TARDANZA and r["hora"] == "08:40"
    assert r["manual"] is True


def test_carga_manual_ausente_sin_hora(con_alumnos):
    """Una ausencia se carga sin hora."""
    r = asistencias.carga_manual(con_alumnos, "45123456", "2026-11-02",
                                 "AUSENTE", "", hoy=HOY)
    assert r["estado"] == AUSENTE and r["hora"] is None


def test_carga_manual_tardanza_pide_hora(con_alumnos):
    """Para una tardanza hace falta la hora de llegada."""
    with pytest.raises(ErrorValidacion, match="hora de llegada"):
        asistencias.carga_manual(con_alumnos, "45123456", "2026-11-02",
                                 "TARDANZA", "", hoy=HOY)


def test_carga_manual_tardanza_antes_del_limite(con_alumnos):
    """Una hora anterior al límite no es tardanza."""
    with pytest.raises(ErrorValidacion, match="no es tardanza"):
        asistencias.carga_manual(con_alumnos, "45123456", "2026-11-02",
                                 "TARDANZA", "08:00", hoy=HOY)


def test_carga_manual_fecha_futura(con_alumnos):
    """No se puede cargar asistencia de una fecha futura."""
    with pytest.raises(ErrorValidacion, match="futura"):
        asistencias.carga_manual(con_alumnos, "45123456", "2026-11-07",
                                 "AUSENTE", "", hoy=HOY)


def test_carga_manual_estado_invalido(con_alumnos):
    """A mano solo se cargan tardanzas o ausencias."""
    with pytest.raises(ErrorValidacion):
        asistencias.carga_manual(con_alumnos, "45123456", "2026-11-02",
                                 "PRESENTE", "08:00", hoy=HOY)


def test_carga_manual_duplicada(con_alumnos):
    """No se puede cargar dos registros del mismo alumno y fecha."""
    asistencias.carga_manual(con_alumnos, "45123456", "2026-11-02",
                             "AUSENTE", "", hoy=HOY)
    with pytest.raises(ErrorValidacion, match="ya tiene un registro"):
        asistencias.carga_manual(con_alumnos, "45123456", "2026-11-02",
                                 "TARDANZA", "09:00", hoy=HOY)


# ---------------- Resumen del día ----------------

def test_resumen_del_dia(con_alumnos):
    """Cuenta presentes, tardanzas y quienes faltan registrarse."""
    asistencias.registrar(con_alumnos, "45123456", ahora=a_las(8, 30))
    resumen = asistencias.resumen_del_dia(con_alumnos, HOY)
    assert resumen["cantidades"] == {PRESENTE: 0, TARDANZA: 1, AUSENTE: 0}
    assert resumen["sin_registrar"] == 1
    assert resumen["registros"][0]["nombre"] == "Juan Pérez"


def test_la_base_impide_dos_registros_del_mismo_dia(con_alumnos,
                                                    monkeypatch):
    """
    Si dos registros llegan juntos y ambos pasan el control en Python,
    la restricción UNIQUE de la base frena al segundo.
    """
    asistencias.registrar(con_alumnos, "45123456", ahora=a_las(8, 0))
    asistencias.carga_manual(con_alumnos, "1234567", "2026-11-02",
                             "AUSENTE", "", hoy=HOY)
    monkeypatch.setattr(asistencias, "_registro_previo",
                        lambda *args, **kwargs: None)
    with pytest.raises(ErrorValidacion, match="ya tiene registrada"):
        asistencias.registrar(con_alumnos, "45123456", ahora=a_las(8, 5))
    with pytest.raises(ErrorValidacion, match="ya tiene un registro"):
        asistencias.carga_manual(con_alumnos, "1234567", "2026-11-02",
                                 "AUSENTE", "", hoy=HOY)
