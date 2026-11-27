"""Tests de las pantallas web: que respondan, que validen y que pidan
login."""
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from asistencia import bd
from asistencia.interfaz import crear_app
from tests.conftest import DOCENTE

RUTAS_PROTEGIDAS = ["/", "/asistencia", "/alumnos", "/informe"]


@pytest.mark.parametrize("ruta", RUTAS_PROTEGIDAS)
def test_paginas_abren(cliente, ruta):
    """Con sesión iniciada, todas las pantallas abren."""
    assert cliente.get(ruta).status_code == 200


def test_flujo_completo(cliente):
    """Alta de alumno, registro, cierre del día e informe."""
    r = cliente.post("/alumnos", data={"dni": "45123456", "nombre": "Juan",
                                       "apellido": "Pérez"},
                     follow_redirects=True)
    assert "Se dio de alta a Juan Pérez" in r.text

    r = cliente.post("/registrar", data={"dni": "45123456"},
                     follow_redirects=True)
    assert "Juan Pérez" in r.text
    assert "resultado-presente" in r.text or "resultado-tardanza" in r.text

    r = cliente.post("/cerrar-dia", follow_redirects=True)
    assert "Día cerrado" in r.text

    r = cliente.get("/informe?dni=45123456")
    assert "Juan Pérez" in r.text and "100.0 %" in r.text

    r = cliente.get("/alumnos")
    assert "100.0" in r.text


def test_carga_manual_y_hora_limite(cliente):
    """La carga manual y el cambio de hora límite muestran su mensaje."""
    cliente.post("/alumnos", data={"dni": "45123456", "nombre": "Juan",
                                   "apellido": "Pérez"})
    r = cliente.post("/hora-limite", data={"hora_limite": "07:30"},
                     follow_redirects=True)
    assert "Hora límite actualizada a las 07:30" in r.text

    r = cliente.post("/manual", data={"dni": "45123456",
                                      "fecha": "2026-01-05",
                                      "estado": "TARDANZA", "hora": "08:00"},
                     follow_redirects=True)
    assert "Se cargó TARDANZA para Juan Pérez el 05/01/2026" in r.text


def test_validacion_en_servidor(cliente):
    """Los datos se validan en el servidor, no solo en el navegador."""
    r = cliente.post("/alumnos", data={"dni": "12ab", "nombre": "",
                                       "apellido": "X"})
    assert r.status_code == 400
    assert "El DNI solo puede tener números" in r.text


def test_dni_inexistente_muestra_mensaje(cliente):
    """Registrar un DNI desconocido muestra un mensaje claro."""
    r = cliente.post("/registrar", data={"dni": "99999999"})
    assert r.status_code == 400 and "No hay ningún alumno" in r.text


def test_formulario_sin_campos_no_rompe(cliente):
    """Formularios vacíos dan 400, nunca un error 500."""
    for ruta in ["/registrar", "/manual", "/hora-limite", "/alumnos"]:
        assert cliente.post(ruta, data={}).status_code == 400


def test_pagina_inexistente(cliente):
    """Una dirección que no existe muestra la página 404 amigable."""
    r = cliente.get("/no-existe")
    assert r.status_code == 404 and "no existe" in r.text


def test_error_de_base_muestra_pagina_amigable(tmp_path):
    """Si la base está dañada, se ve un mensaje claro y no un error de
    Python."""
    ruta = tmp_path / "danada.db"
    ruta.write_bytes(b"esto no es una base de datos SQLite" * 100)
    app = crear_app(str(ruta), clave_secreta="clave-de-prueba")
    with TestClient(app, raise_server_exceptions=False) as cliente_web:
        r = cliente_web.get("/login")
    assert r.status_code == 500
    assert "No se pudo acceder a la base de datos" in r.text


def test_envio_demasiado_grande(cliente):
    """Los envíos de más de 16 KB se rechazan con 413."""
    r = cliente.post("/alumnos", data={"nombre": "x" * 20000})
    assert r.status_code == 413 and "demasiado grandes" in r.text


# ----------------------------------------------------------------------
# Login
# ----------------------------------------------------------------------

@pytest.mark.parametrize("ruta", RUTAS_PROTEGIDAS)
def test_sin_login_redirige_al_login(anonimo, ruta):
    """Sin sesión, las pantallas protegidas llevan al login."""
    r = anonimo.get(ruta)
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")


def test_sin_login_no_se_puede_registrar_asistencia(anonimo):
    """Sin sesión tampoco se puede enviar ningún formulario."""
    r = anonimo.post("/registrar", data={"dni": "45123456"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")


@pytest.mark.parametrize("ruta", ["/login", "/registro-docente"])
def test_paginas_de_acceso_abren_sin_login(anonimo, ruta):
    """El login y la creación de cuenta abren sin sesión."""
    r = anonimo.get(ruta)
    assert r.status_code == 200 and "pagina-acceso" in r.text


def test_con_sesion_el_login_lleva_al_dashboard(cliente):
    """Si ya hay sesión, entrar al login lleva al dashboard."""
    r = cliente.get("/login")
    assert r.status_code == 302 and r.headers["Location"] == "/"


def test_registro_saluda_al_docente_por_su_nombre(anonimo):
    """Al crear la cuenta queda la sesión iniciada con su nombre."""
    r = anonimo.post("/registro-docente", data=DOCENTE,
                     follow_redirects=True)
    assert "Bienvenido docente" in r.text and "María González" in r.text


def test_login_correcto_detecta_al_docente(anonimo):
    """Cada docente ve su propio nombre al entrar."""
    anonimo.post("/registro-docente", data=DOCENTE)
    anonimo.post("/logout")
    otro = {**DOCENTE, "email": "pedro.ruiz@escuela.edu.ar",
            "nombre": "Pedro", "apellido": "Ruiz"}
    anonimo.post("/registro-docente", data=otro)
    anonimo.post("/logout")

    r = anonimo.post("/login",
                     data={"email": "  Pedro.Ruiz@Escuela.edu.ar ",
                           "clave": "Clave123!"},
                     follow_redirects=True)
    assert "Bienvenido docente" in r.text and "Pedro Ruiz" in r.text
    assert "María González" not in r.text


@pytest.mark.parametrize("email, clave", [
    ("maria.gonzalez@escuela.edu.ar", "Incorrecta1!"),
    ("nadie@escuela.edu.ar", "Clave123!"),
])
def test_login_incorrecto(cliente, email, clave):
    """Con datos incorrectos no se inicia sesión."""
    cliente.post("/logout")
    r = cliente.post("/login", data={"email": email, "clave": clave})
    assert r.status_code == 400
    assert "El email o la contraseña no son correctos" in r.text
    assert cliente.get("/").status_code == 302


def test_logout_cierra_la_sesion(cliente):
    """Después de cerrar sesión, las pantallas vuelven a pedir login."""
    r = cliente.post("/logout", follow_redirects=True)
    assert "Cerraste la sesión" in r.text
    assert cliente.get("/").status_code == 302


def test_la_clave_no_se_guarda_tal_cual(cliente, ruta_memoria):
    """En la base queda el hash de la clave, no la clave."""
    with closing(bd.conectar(ruta_memoria)) as conexion:
        fila = conexion.execute(
            "SELECT email, clave_hash FROM usuarios").fetchone()
    assert fila["email"] == DOCENTE["email"]
    assert DOCENTE["clave"] not in fila["clave_hash"]


@pytest.mark.parametrize("clave, mensaje", [
    ("Ab1!", "al menos 8 caracteres"),
    ("12345678!", "al menos una letra"),
    ("Abcdefgh!", "al menos un número"),
    ("Abcdefg12", "al menos un carácter especial"),
])
def test_registro_exige_clave_segura(anonimo, clave, mensaje):
    """La pantalla de registro muestra por qué la clave no sirve."""
    r = anonimo.post("/registro-docente",
                     data={**DOCENTE, "clave": clave,
                           "clave_repetida": clave})
    assert r.status_code == 400 and mensaje in r.text


def test_registro_claves_distintas(anonimo):
    """Si las dos claves no coinciden, se avisa."""
    r = anonimo.post("/registro-docente",
                     data={**DOCENTE, "clave_repetida": "Otra123!"})
    assert r.status_code == 400 and "no coinciden" in r.text


def test_registro_email_repetido(cliente):
    """No se puede crear dos cuentas con el mismo email."""
    cliente.post("/logout")
    r = cliente.post("/registro-docente", data=DOCENTE)
    assert r.status_code == 400 and "Ya existe una cuenta" in r.text


def test_registro_email_invalido(anonimo):
    """Un email mal escrito se rechaza."""
    r = anonimo.post("/registro-docente", data={**DOCENTE, "email": "maria@"})
    assert r.status_code == 400 and "El email no es válido" in r.text


def test_usuario_borrado_pierde_la_sesion(cliente, ruta_memoria):
    """Si la cuenta se borra de la base, la sesión deja de valer."""
    with closing(bd.conectar(ruta_memoria)) as conexion:
        conexion.execute("DELETE FROM usuarios")
    assert cliente.get("/").status_code == 302


# ----------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------

def test_login_lleva_al_dashboard(anonimo):
    """Después de entrar se ve el dashboard."""
    r = anonimo.post("/registro-docente", data=DOCENTE)
    assert r.status_code == 302 and r.headers["Location"] == "/"
    r = anonimo.get("/")
    assert "Dashboard" in r.text and "Bienvenido docente" in r.text


def test_dashboard_vacio(cliente):
    """Sin registros, el dashboard lo dice."""
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Todavía no hay asistencias registradas" in r.text


def test_dashboard_muestra_grafico_y_ranking(cliente):
    """Con registros aparecen el gráfico, el ranking y el porcentaje."""
    cliente.post("/alumnos", data={"dni": "45123456", "nombre": "Juan",
                                   "apellido": "Pérez"})
    cliente.post("/alumnos", data={"dni": "40111222", "nombre": "Ana",
                                   "apellido": "Díaz"})
    cliente.post("/registrar", data={"dni": "45123456"})
    cliente.post("/cerrar-dia")      # Ana queda AUSENTE

    pagina = cliente.get("/").text
    assert 'id="grafico-dias"' in pagina
    assert "Más ausencias" in pagina and "Ana Díaz" in pagina
    assert "Asistencia general: <strong>50.0 %</strong>" in pagina


def test_la_base_real_no_se_usa_en_los_tests(ruta_memoria):
    """Los tests usan una base en memoria, nunca datos/asistencia.db."""
    assert "mode=memory" in ruta_memoria
    with closing(sqlite3.connect(ruta_memoria, uri=True)) as conexion:
        assert conexion.execute("PRAGMA user_version").fetchone()[0] >= 1
