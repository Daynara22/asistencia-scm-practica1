"""
Fixtures compartidas por todos los tests.

Ningún test toca la base real (datos/asistencia.db): cada uno usa su
propia base SQLite en memoria, que desaparece al terminar el test.
"""
import uuid
from contextlib import closing
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from asistencia import bd
from asistencia.interfaz import crear_app
from asistencia.servicios import alumnos

HOY = date(2026, 11, 6)

DOCENTE = {
    "email": "maria.gonzalez@escuela.edu.ar",
    "nombre": "María",
    "apellido": "González",
    "clave": "Clave123!",
    "clave_repetida": "Clave123!",
}


def a_las(hora, minuto, dia=HOY):
    """Fecha y hora de prueba: el día indicado (HOY por defecto) a esa
    hora."""
    return datetime(dia.year, dia.month, dia.day, hora, minuto)


@pytest.fixture
def conexion():
    """Conexión a una base vacía en memoria, con el esquema creado."""
    with closing(bd.conectar(":memory:")) as conexion_prueba:
        yield conexion_prueba


@pytest.fixture
def con_alumnos(conexion):
    """Base en memoria con dos alumnos y la hora límite en 08:15."""
    alumnos.alta(conexion, "45123456", "juan", "pérez")
    alumnos.alta(conexion, "1234567", "Ana", "Gómez")
    return conexion


@pytest.fixture
def ruta_memoria():
    """
    URI de una base en memoria compartida entre conexiones.

    La aplicación web abre una conexión por request; con
    "cache=shared" todas ven la misma base. La conexión que queda
    abierta durante el test evita que la base se borre entre requests.
    """
    ruta = f"file:prueba-{uuid.uuid4().hex}?mode=memory&cache=shared"
    with closing(bd.conectar(ruta)):
        yield ruta


@pytest.fixture
def anonimo(ruta_memoria):
    """Cliente web sin sesión iniciada."""
    app = crear_app(ruta_memoria, clave_secreta="clave-de-prueba")
    # follow_redirects=False: así los tests pueden revisar las
    # redirecciones (302).
    with TestClient(app, follow_redirects=False) as cliente_web:
        yield cliente_web


@pytest.fixture
def cliente(anonimo):
    """Cliente web con un docente registrado y la sesión iniciada."""
    anonimo.post("/registro-docente", data=DOCENTE)
    return anonimo
