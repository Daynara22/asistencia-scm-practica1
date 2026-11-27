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
from asistencia.servicios import alumnos, cursos, docentes

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

# Docente y curso que se crean en todas las bases de prueba, porque para
# dar de alta un alumno hace falta un curso.
CURSO_ID = 1


def datos_alumno(dni, nombre, apellido, curso_id=CURSO_ID):
    """Datos del formulario de alta de un alumno (con email y curso)."""
    return {"dni": dni, "nombre": nombre, "apellido": apellido,
            "email": f"{dni}@alumnos.edu.ar", "curso_id": str(curso_id)}


def crear_curso(conexion, nombre="Programación", division="A"):
    """Crea un docente (si no hay) y un curso a su cargo. Devuelve el
    curso."""
    fila = conexion.execute("SELECT id FROM docentes LIMIT 1").fetchone()
    if fila:
        docente_id = fila["id"]
    else:
        docente_id = docentes.alta(conexion, "30111222", "Laura", "Sosa",
                                   "laura.sosa@escuela.edu.ar",
                                   "Matemática, Física").id
    return cursos.alta(conexion, nombre, 3, division, docente_id)


def alta_alumno(conexion, dni, nombre, apellido, curso_id=CURSO_ID):
    """Da de alta un alumno con email y curso de prueba."""
    datos = datos_alumno(dni, nombre, apellido, curso_id)
    return alumnos.alta(conexion, datos["dni"], datos["nombre"],
                        datos["apellido"], datos["email"],
                        datos["curso_id"])


ALUMNO = datos_alumno("45123456", "Juan", "Pérez")
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
def con_curso(conexion):
    """Base en memoria con un docente y un curso (id CURSO_ID)."""
    crear_curso(conexion)
    return conexion


@pytest.fixture
def con_alumnos(con_curso):
    """Base en memoria con dos alumnos y la hora límite en 08:15."""
    alta_alumno(con_curso, "45123456", "juan", "pérez")
    alta_alumno(con_curso, "1234567", "Ana", "Gómez")
    return con_curso


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
def cliente(anonimo, ruta_memoria):
    """
    Cliente web con sesión de administrador (la primera cuenta).

    La base ya tiene un docente y un curso, para poder dar de alta
    alumnos.
    """
    anonimo.post("/registro-docente", data=DOCENTE)
    with closing(bd.conectar(ruta_memoria)) as conexion:
        crear_curso(conexion)
    return anonimo


@pytest.fixture
def cliente_docente(anonimo, ruta_memoria):
    """
    Cliente web con sesión de docente (sin permisos de administrador).

    La primera cuenta queda como administradora, así que se crea una
    primero y después se entra con una segunda cuenta.
    """
    anonimo.post("/registro-docente", data=DOCENTE)
    anonimo.post("/logout")
    anonimo.post("/registro-docente", data=OTRO_DOCENTE)
    with closing(bd.conectar(ruta_memoria)) as conexion:
        crear_curso(conexion)
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
