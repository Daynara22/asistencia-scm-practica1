"""Tests de bd.py: esquema, transacciones y acceso concurrente."""
import sqlite3
import threading
from contextlib import closing

import pytest

from asistencia import bd
from asistencia.servicios import alumnos, asistencias
from tests.conftest import a_las, alta_alumno, crear_curso


def test_esquema_se_crea_con_la_version_actual(conexion):
    """Una base nueva queda en la última versión del esquema."""
    version = conexion.execute("PRAGMA user_version").fetchone()[0]
    assert version == len(bd.MIGRACIONES)
    tablas = {fila["name"] for fila in conexion.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"alumnos", "asistencias", "usuarios", "configuracion",
            "dias_cerrados"} <= tablas


def test_crear_esquema_dos_veces_no_falla(conexion):
    """Volver a aplicar el esquema sobre una base al día no hace nada."""
    bd.crear_esquema(conexion)
    assert conexion.execute("PRAGMA user_version").fetchone()[0] == \
        len(bd.MIGRACIONES)


def test_transaccion_deshace_si_hay_error(conexion):
    """Si algo falla dentro de la transacción, no se guarda nada."""
    with pytest.raises(RuntimeError):
        with bd.transaccion(conexion):
            conexion.execute("INSERT INTO alumnos (dni, nombre, apellido) "
                             "VALUES ('40111222', 'Ana', 'Díaz')")
            raise RuntimeError("falla a propósito")
    assert alumnos.cantidad(conexion) == 0


def test_claves_foraneas_activadas(conexion):
    """No se puede guardar asistencia de un alumno inexistente."""
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("INSERT INTO asistencias (alumno_id, fecha, estado)"
                         " VALUES (999, '2026-11-06', 'PRESENTE')")


def test_base_en_archivo_usa_wal(tmp_path):
    """En un archivo se activa el modo WAL (lecturas y escrituras a la
    vez)."""
    with closing(bd.conectar(str(tmp_path / "prueba.db"))) as conexion:
        modo = conexion.execute("PRAGMA journal_mode").fetchone()[0]
    assert modo == "wal"


def test_segunda_escritura_espera_a_la_primera(tmp_path, monkeypatch):
    """Mientras un usuario guarda, otro no puede pisar sus cambios."""
    ruta = str(tmp_path / "prueba.db")
    monkeypatch.setattr(bd, "TIEMPO_ESPERA", 0)   # no esperar en el test
    with closing(bd.conectar(ruta)) as primera, \
            closing(bd.conectar(ruta)) as segunda:
        with bd.transaccion(primera):
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                with bd.transaccion(segunda):
                    pass
        # Cuando la primera termina, la segunda ya puede escribir.
        with bd.transaccion(segunda):
            pass


def test_registros_simultaneos_de_varios_usuarios(tmp_path):
    """Varios usuarios registrando a la vez: no se pierde ningún
    registro."""
    ruta = str(tmp_path / "prueba.db")
    dnis = [str(40000000 + i) for i in range(10)]
    with closing(bd.conectar(ruta)) as conexion:
        crear_curso(conexion)
        for dni in dnis:
            alta_alumno(conexion, dni, "Alumno", "Prueba")

    errores = []

    def registrar(dni):
        """Cada hilo simula un usuario con su propia conexión."""
        try:
            with closing(bd.conectar(ruta)) as propia:
                asistencias.registrar(propia, dni, ahora=a_las(8, 0))
        except Exception as error:      # se revisa al final del test
            errores.append(error)

    hilos = [threading.Thread(target=registrar, args=(dni,))
             for dni in dnis]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert errores == []
    with closing(bd.conectar(ruta)) as conexion:
        total = conexion.execute(
            "SELECT COUNT(*) FROM asistencias").fetchone()[0]
    assert total == len(dnis)
