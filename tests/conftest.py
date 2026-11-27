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

from asistencia import bd, seguridad
from asistencia.interfaz import crear_app
from asistencia.servicios import alumnos

HOY = date(2026, 11, 6)

CLAVE = "Clave123!"

DOCENTE = {
    "email": "maria.gonzalez@escuela.edu.ar",
    "nombre": "María",
    "apellido": "González",
    "clave": CLAVE,
    "clave_repetida": CLAVE,
}

OTRO_DOCENTE = {**DOCENTE, "email": "pedro.ruiz@escuela.edu.ar",
                "nombre": "Pedro", "apellido": "Ruiz"}

ALUMNO = {"dni": "45123456", "nombre": "Juan", "apellido": "Pérez"}
EMAIL_ALUMNO = "juan.perez@alumnos.edu.ar"


def a_las(hora, minuto, dia=HOY):
    """Fecha y hora de prueba: el día indicado (HOY por defecto) a esa
    hora."""
    return datetime(dia.year, dia.month, dia.day, hora, minuto)


@pytest.fixture(autouse=True)
def hash_rapido(monkeypatch):
    """
    Baja el costo de scrypt durante los tests para que corran rápido.

    El hash guarda sus propios parámetros ("scrypt:N:r:p$..."), así que
    la verificación es la misma que en producción.
    """
    monkeypatch.setattr(seguridad, "SCRYPT_N", 2 ** 10)


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


@pytest.fixture
def cliente_docente(anonimo):
    """
    Cliente web con sesión de docente (sin permisos de administrador).

    La primera cuenta queda como administradora, así que se crea una
    primero y después se entra con una segunda cuenta.
    """
    anonimo.post("/registro-docente", data=DOCENTE)
    anonimo.post("/logout")
    anonimo.post("/registro-docente", data=OTRO_DOCENTE)
    return anonimo


@pytest.fixture
def cliente_alumno(cliente):
    """
    Cliente web con sesión de alumno.

    El administrador da de alta al alumno, le crea la cuenta y cierra su
    sesión; después el alumno entra con su email.
    """
    cliente.post("/alumnos", data=ALUMNO)
    cliente.post("/usuarios/alumno",
                 data={"dni": ALUMNO["dni"], "email": EMAIL_ALUMNO,
                       "clave": CLAVE, "clave_repetida": CLAVE})
    cliente.post("/logout")
    cliente.post("/login", data={"email": EMAIL_ALUMNO, "clave": CLAVE})
    return cliente
