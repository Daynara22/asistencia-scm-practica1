"""Tests de las pantallas web: que respondan, que validen y que pidan
login."""
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from asistencia import bd
from asistencia.interfaz import comun, rutas_asistencia
from asistencia.interfaz import crear_app
from tests.conftest import DOCENTE, datos_alumno

RUTAS_PROTEGIDAS = ["/", "/asistencia", "/alumnos", "/informe"]


@pytest.mark.parametrize("ruta", RUTAS_PROTEGIDAS)
def test_paginas_abren(cliente, ruta):
    """Con sesión iniciada, todas las pantallas abren."""
    assert cliente.get(ruta).status_code == 200


def test_flujo_completo(cliente):
    """Alta de alumno, registro, cierre del día e informe."""
    juan = datos_alumno("45123456", "Juan", "Pérez")
    r = cliente.post("/alumnos", data=juan,
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
    cliente.post("/alumnos", data=datos_alumno("45123456", "Juan", "Pérez"))
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


def test_registro_saluda_por_su_nombre(anonimo):
    """Al crear la cuenta queda la sesión iniciada con su nombre.

    Es la primera cuenta de la base, así que queda como administrador.
    """
    r = anonimo.post("/registro-docente", data=DOCENTE,
                     follow_redirects=True)
    assert "Bienvenido administrador" in r.text
    assert "María González" in r.text


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
    assert "Dashboard" in r.text and "Bienvenido administrador" in r.text


def test_dashboard_vacio(cliente):
    """Sin registros, el dashboard lo dice."""
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Todavía no hay asistencias registradas" in r.text


def test_dashboard_muestra_grafico_y_ranking(cliente):
    """Con registros aparecen el gráfico, el ranking y el porcentaje."""
    cliente.post("/alumnos", data=datos_alumno("45123456", "Juan", "Pérez"))
    cliente.post("/alumnos", data=datos_alumno("40111222", "Ana", "Díaz"))
    cliente.post("/registrar", data={"dni": "45123456"})
    cliente.post("/cerrar-dia")      # Ana queda AUSENTE

    pagina = cliente.get("/").text
    assert 'id="grafico-dias"' in pagina
    assert "Más ausencias" in pagina and "Ana Díaz" in pagina
    assert 'id="tarjetas-resumen"' in pagina
    assert '<span class="kpi-valor">50.0%</span>' in pagina


def test_la_base_real_no_se_usa_en_los_tests(ruta_memoria):
    """Los tests usan una base en memoria, nunca datos/asistencia.db."""
    assert "mode=memory" in ruta_memoria
    with closing(sqlite3.connect(ruta_memoria, uri=True)) as conexion:
        assert conexion.execute("PRAGMA user_version").fetchone()[0] >= 1


# ----------------------------------------------------------------------
# Casos borde de la interfaz
# ----------------------------------------------------------------------

def test_punto_de_entrada_crea_la_aplicacion(monkeypatch, tmp_path):
    """app.py arma la aplicación con la base de ASISTENCIA_BD."""
    import importlib

    import app as modulo_app
    monkeypatch.setenv("ASISTENCIA_BD", str(tmp_path / "entrada.db"))
    importlib.reload(modulo_app)
    assert modulo_app.app.state.ruta_bd == str(tmp_path / "entrada.db")


def test_con_sesion_registro_lleva_al_dashboard(cliente):
    """Si ya hay sesión, la pantalla de crear cuenta lleva al inicio."""
    r = cliente.get("/registro-docente")
    assert r.status_code == 302 and r.headers["Location"] == "/"


def test_cerrar_el_dia_dos_veces(cliente):
    """La segunda vez avisa que el día ya estaba cerrado."""
    cliente.post("/cerrar-dia")
    r = cliente.post("/cerrar-dia")
    assert r.status_code == 400 and "ya estaba cerrado" in r.text


def test_error_inesperado_muestra_pagina_amigable(ruta_memoria,
                                                  monkeypatch):
    """Un error de programación no muestra el detalle técnico."""
    def falla(*args, **kwargs):
        """Simula un error que nadie esperaba."""
        raise RuntimeError("detalle interno que no se debe ver")

    monkeypatch.setattr(rutas_asistencia.informes, "resumen_general", falla)
    app = crear_app(ruta_memoria, clave_secreta="clave-de-prueba")
    with TestClient(app, raise_server_exceptions=False) as cliente_web:
        cliente_web.post("/registro-docente", data=DOCENTE)
        r = cliente_web.get("/")
    assert r.status_code == 500
    assert "Ocurrió un error inesperado" in r.text
    assert "detalle interno" not in r.text


def test_version_estaticos_sin_archivos(monkeypatch):
    """Si no encuentra el CSS o el JS, la versión es 0 (no falla)."""
    monkeypatch.setattr(comun, "CARPETA_ESTATICOS", "/carpeta/inexistente")
    assert comun.version_estaticos() == 0


def test_ruta_con_id_que_la_ruta_no_usa(cliente):
    """Si la ruta no lleva {id}, el id va después del "?"."""
    request = Request({"type": "http", "app": cliente.app})
    assert comun.ruta_de(request, "alumnos", id=3) == "/alumnos?id=3"
    assert comun.ruta_de(request, "modificar_alumno", id=3) == \
        "/alumnos/3"
    assert comun.ruta_de(request, "informe", dni="1", desde="") == \
        "/informe?dni=1"


def test_usuario_sin_sesion_en_pagina_de_error(cliente):
    """Sin sesión en el pedido, la página de error sigue sin usuario."""
    request = Request({"type": "http", "app": cliente.app})
    assert comun.buscar_usuario_sin_conexion(request) is None
    # Y los mensajes pendientes quedan vacíos en lugar de fallar.
    assert comun.get_flashed_messages({"request": request}) == []
