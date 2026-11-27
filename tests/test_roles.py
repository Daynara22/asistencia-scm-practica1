"""
Tests de roles y permisos: administrador, docente y alumno.

Incluye las reglas del servicio de usuarios (primer usuario
administrador, cuentas de alumno, cambio de rol), qué pantallas puede
abrir cada rol y el script gestionar_usuarios.py.
"""
import sqlite3
from contextlib import closing

import pytest

import gestionar_usuarios
from asistencia import bd
from asistencia.modelos import ADMINISTRADOR, ALUMNO, DOCENTE
from asistencia.servicios import alumnos, asistencias, usuarios
from asistencia.validaciones import ErrorValidacion
from tests.conftest import (CLAVE, DOCENTE as DATOS_DOCENTE, EMAIL_ALUMNO,
                            OTRO_DOCENTE, a_las, alta_alumno, crear_curso,
                            datos_alumno)

PANTALLAS_DE_DOCENTE = ["/", "/asistencia", "/alumnos", "/informe"]
ENVIOS_DE_DOCENTE = ["/registrar", "/manual", "/hora-limite", "/cerrar-dia",
                     "/alumnos"]
PANTALLAS_DE_ADMIN = ["/usuarios"]
ENVIOS_DE_ADMIN = ["/usuarios/rol", "/usuarios/alumno"]


def registrar(conexion, datos):
    """Registra una cuenta de docente con los datos indicados."""
    return usuarios.registrar_docente(
        conexion, datos["email"], datos["nombre"], datos["apellido"],
        datos["clave"], datos["clave_repetida"])


@pytest.fixture
def con_cuentas(conexion):
    """Base con un administrador, un docente y un alumno sin cuenta."""
    registrar(conexion, DATOS_DOCENTE)
    registrar(conexion, OTRO_DOCENTE)
    crear_curso(conexion)
    alta_alumno(conexion, "45123456", "Juan", "Pérez")
    return conexion


# ----------------------------------------------------------------------
# Servicio de usuarios
# ----------------------------------------------------------------------

def test_primer_usuario_es_administrador(conexion):
    """La primera cuenta es administradora; las siguientes, docentes."""
    primero = registrar(conexion, DATOS_DOCENTE)
    segundo = registrar(conexion, OTRO_DOCENTE)
    assert primero.rol == ADMINISTRADOR and primero.es_administrador
    assert segundo.rol == DOCENTE and not segundo.es_administrador


def test_rol_invalido_no_se_puede_guardar(conexion):
    """La base solo acepta los tres roles definidos."""
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute(
            "INSERT INTO usuarios (email, nombre, apellido, clave_hash, rol)"
            " VALUES ('x@y.com', 'X', 'Y', 'h', 'superusuario')")


def test_crear_cuenta_de_alumno(con_cuentas):
    """La cuenta de alumno toma el nombre del alumno y queda
    vinculada."""
    cuenta = usuarios.crear_cuenta_alumno(con_cuentas, "45.123.456",
                                          EMAIL_ALUMNO, CLAVE, CLAVE)
    alumno = alumnos.buscar_por_dni(con_cuentas, "45123456")
    assert cuenta.rol == ALUMNO and cuenta.es_alumno
    assert cuenta.alumno_id == alumno.id
    assert cuenta.nombre_completo == "Juan Pérez"
    assert usuarios.autenticar(con_cuentas, EMAIL_ALUMNO, CLAVE).es_alumno


def test_cuenta_de_alumno_inexistente(con_cuentas):
    """No se crea cuenta para un DNI que no está dado de alta."""
    with pytest.raises(ErrorValidacion, match="No hay ningún alumno"):
        usuarios.crear_cuenta_alumno(con_cuentas, "99999999",
                                     EMAIL_ALUMNO, CLAVE, CLAVE)


def test_una_sola_cuenta_por_alumno(con_cuentas):
    """Un alumno no puede tener dos cuentas."""
    usuarios.crear_cuenta_alumno(con_cuentas, "45123456", EMAIL_ALUMNO,
                                 CLAVE, CLAVE)
    with pytest.raises(ErrorValidacion, match="ya tiene una cuenta"):
        usuarios.crear_cuenta_alumno(con_cuentas, "45123456",
                                     "otro@alumnos.edu.ar", CLAVE, CLAVE)


def test_cuenta_de_alumno_con_email_repetido(con_cuentas):
    """El email de la cuenta de alumno no puede estar usado."""
    with pytest.raises(ErrorValidacion, match="Ya existe una cuenta"):
        usuarios.crear_cuenta_alumno(con_cuentas, "45123456",
                                     DATOS_DOCENTE["email"], CLAVE, CLAVE)


def test_cambiar_rol_de_docente_a_administrador(con_cuentas):
    """Un docente puede pasar a administrador y volver."""
    pedro = usuarios.autenticar(con_cuentas, OTRO_DOCENTE["email"], CLAVE)
    assert usuarios.cambiar_rol(con_cuentas, pedro.id,
                                ADMINISTRADOR).es_administrador
    assert usuarios.cambiar_rol(con_cuentas, pedro.id, DOCENTE).rol == \
        DOCENTE


def test_no_se_quita_el_ultimo_administrador(con_cuentas):
    """Siempre queda al menos un administrador."""
    maria = usuarios.autenticar(con_cuentas, DATOS_DOCENTE["email"], CLAVE)
    with pytest.raises(ErrorValidacion, match="al menos un administrador"):
        usuarios.cambiar_rol(con_cuentas, maria.id, DOCENTE)
    assert usuarios.obtener(con_cuentas, maria.id).es_administrador


def test_cuenta_de_alumno_no_cambia_de_rol(con_cuentas):
    """Un alumno no puede convertirse en docente ni administrador."""
    cuenta = usuarios.crear_cuenta_alumno(con_cuentas, "45123456",
                                          EMAIL_ALUMNO, CLAVE, CLAVE)
    with pytest.raises(ErrorValidacion, match="no pueden cambiar de rol"):
        usuarios.cambiar_rol(con_cuentas, cuenta.id, ADMINISTRADOR)


@pytest.mark.parametrize("usuario_id, rol", [
    (999, DOCENTE), ("abc", DOCENTE), (1, ALUMNO), (1, "superusuario")])
def test_cambiar_rol_con_datos_invalidos(con_cuentas, usuario_id, rol):
    """Cuenta inexistente o rol no permitido dan error de validación."""
    with pytest.raises(ErrorValidacion):
        usuarios.cambiar_rol(con_cuentas, usuario_id, rol)


def test_listar_no_muestra_el_hash(con_cuentas):
    """El listado de cuentas no incluye el hash de la contraseña."""
    cuentas = usuarios.listar(con_cuentas)
    assert len(cuentas) == 2
    assert all("clave_hash" not in cuenta for cuenta in cuentas)
    assert {c["nombre_rol"] for c in cuentas} == {"Administrador",
                                                  "Docente"}


def test_migracion_de_roles_deja_docentes(tmp_path):
    """Una base de la versión 1 pasa a la 2 con sus cuentas como
    docentes."""
    ruta = str(tmp_path / "vieja.db")
    # Se arma a mano una base con solo la primera versión del esquema.
    with closing(sqlite3.connect(ruta, isolation_level=None)) as vieja:
        for sentencia in bd.MIGRACIONES[0]:
            vieja.execute(sentencia)
        vieja.execute("PRAGMA user_version = 1")
        vieja.execute("INSERT INTO usuarios (email, nombre, apellido, "
                      "clave_hash) VALUES ('a@b.com', 'Ana', 'Díaz', 'h')")
    with closing(bd.conectar(ruta)) as conexion:
        fila = conexion.execute("SELECT rol FROM usuarios").fetchone()
        version = conexion.execute("PRAGMA user_version").fetchone()[0]
    assert fila["rol"] == DOCENTE
    assert version == len(bd.MIGRACIONES)


# ----------------------------------------------------------------------
# Permisos en la web
# ----------------------------------------------------------------------

@pytest.mark.parametrize("ruta", PANTALLAS_DE_DOCENTE + PANTALLAS_DE_ADMIN)
def test_administrador_entra_a_todo(cliente, ruta):
    """El administrador abre todas las pantallas."""
    assert cliente.get(ruta).status_code == 200


@pytest.mark.parametrize("ruta", PANTALLAS_DE_DOCENTE)
def test_docente_entra_a_sus_pantallas(cliente_docente, ruta):
    """El docente abre las pantallas de asistencia, alumnos e informes."""
    assert cliente_docente.get(ruta).status_code == 200


@pytest.mark.parametrize("ruta", PANTALLAS_DE_ADMIN)
def test_docente_no_entra_a_usuarios(cliente_docente, ruta):
    """El docente no puede gestionar cuentas."""
    r = cliente_docente.get(ruta)
    assert r.status_code == 403 and "No tenés permiso" in r.text


@pytest.mark.parametrize("ruta", ENVIOS_DE_ADMIN)
def test_docente_no_puede_enviar_formularios_de_admin(cliente_docente,
                                                      ruta):
    """Tampoco puede usar los formularios de administrador
    directamente."""
    assert cliente_docente.post(ruta, data={}).status_code == 403


def test_menu_de_docente_no_muestra_usuarios(cliente_docente):
    """El docente no ve el enlace a Usuarios en el menú."""
    r = cliente_docente.get("/")
    assert "Bienvenido docente" in r.text and "Pedro Ruiz" in r.text
    assert 'href="/usuarios"' not in r.text


def test_menu_de_administrador_muestra_usuarios(cliente):
    """El administrador ve el enlace a Usuarios."""
    assert 'href="/usuarios"' in cliente.get("/").text


def test_alumno_va_directo_a_su_asistencia(cliente_alumno):
    """Al entrar, el alumno va a su informe en lugar del dashboard."""
    r = cliente_alumno.get("/")
    assert r.status_code == 302
    assert r.headers["Location"] == "/mi-asistencia"
    r = cliente_alumno.get("/mi-asistencia")
    assert r.status_code == 200
    assert "Mi asistencia" in r.text and "Juan Pérez" in r.text
    assert "Bienvenido alumno" in r.text
    assert 'name="dni"' not in r.text        # no tiene buscador


@pytest.mark.parametrize("ruta", PANTALLAS_DE_DOCENTE[1:]
                         + PANTALLAS_DE_ADMIN)
def test_alumno_no_entra_a_otras_pantallas(cliente_alumno, ruta):
    """El alumno no ve la información de otros alumnos."""
    r = cliente_alumno.get(ruta)
    assert r.status_code == 403 and "No tenés permiso" in r.text


@pytest.mark.parametrize("ruta", ENVIOS_DE_DOCENTE + ENVIOS_DE_ADMIN)
def test_alumno_no_puede_enviar_formularios(cliente_alumno, ruta):
    """El alumno no puede registrar asistencia ni cambiar nada."""
    assert cliente_alumno.post(ruta, data={"dni": "45123456"}) \
        .status_code == 403


def test_docente_no_entra_a_mi_asistencia(cliente_docente):
    """"Mi asistencia" es solo para alumnos."""
    assert cliente_docente.get("/mi-asistencia").status_code == 403


def test_informe_del_alumno_muestra_sus_datos(cliente_alumno, ruta_memoria):
    """El alumno ve sus propios registros de asistencia."""
    with closing(bd.conectar(ruta_memoria)) as conexion:
        asistencias.registrar(conexion, "45123456", ahora=a_las(8, 0))
    r = cliente_alumno.get("/mi-asistencia")
    assert "100.0 %" in r.text and "PRESENTE" in r.text


def test_pantalla_usuarios_crea_cuenta_de_alumno(cliente):
    """Desde Usuarios, el administrador crea la cuenta de un alumno."""
    cliente.post("/alumnos", data=datos_alumno("40111222", "Ana", "Díaz"))
    r = cliente.post("/usuarios/alumno",
                     data={"dni": "40111222", "email": "ana@alumnos.edu.ar",
                           "clave": CLAVE, "clave_repetida": CLAVE},
                     follow_redirects=True)
    assert "Se creó la cuenta de Ana Díaz" in r.text
    assert "ana@alumnos.edu.ar" in r.text


def test_pantalla_usuarios_muestra_errores(cliente):
    """Si los datos de la cuenta no sirven, se explica por qué."""
    cliente.post("/alumnos", data=datos_alumno("40111222", "Ana", "Díaz"))
    r = cliente.post("/usuarios/alumno",
                     data={"dni": "40111222", "email": "ana@",
                           "clave": CLAVE, "clave_repetida": CLAVE})
    assert r.status_code == 400 and "El email no es válido" in r.text


def test_pantalla_usuarios_cambia_rol(cliente_docente):
    """El administrador hace administrador a un docente desde la
    pantalla."""
    cliente = cliente_docente
    cliente.post("/logout")
    cliente.post("/login", data={"email": DATOS_DOCENTE["email"],
                                 "clave": CLAVE})
    pagina = cliente.get("/usuarios").text
    assert "Hacer administrador" in pagina
    r = cliente.post("/usuarios/rol", data={"usuario_id": "2",
                                            "rol": ADMINISTRADOR},
                     follow_redirects=True)
    assert "Pedro Ruiz ahora es administrador" in r.text


def test_administrador_se_quita_el_rol(cliente_docente):
    """Si el administrador se pasa a docente, vuelve al dashboard."""
    cliente = cliente_docente
    cliente.post("/logout")
    cliente.post("/login", data={"email": DATOS_DOCENTE["email"],
                                 "clave": CLAVE})
    cliente.post("/usuarios/rol", data={"usuario_id": "2",
                                        "rol": ADMINISTRADOR})
    r = cliente.post("/usuarios/rol", data={"usuario_id": "1",
                                            "rol": DOCENTE})
    assert r.status_code == 302 and r.headers["Location"] == "/"
    assert cliente.get("/usuarios").status_code == 403


def test_ultimo_administrador_desde_la_pantalla(cliente):
    """La pantalla avisa si se intenta quitar el último
    administrador."""
    r = cliente.post("/usuarios/rol", data={"usuario_id": "1",
                                            "rol": DOCENTE})
    assert r.status_code == 400 and "al menos un administrador" in r.text


# ----------------------------------------------------------------------
# Script gestionar_usuarios.py
# ----------------------------------------------------------------------

def test_script_hacer_admin(tmp_path, monkeypatch, capsys):
    """El script da el rol de administrador a una cuenta por email."""
    ruta = str(tmp_path / "script.db")
    monkeypatch.setenv("ASISTENCIA_BD", ruta)
    with closing(bd.conectar(ruta)) as conexion:
        registrar(conexion, DATOS_DOCENTE)
        registrar(conexion, OTRO_DOCENTE)

    assert gestionar_usuarios.main(["hacer-admin",
                                    OTRO_DOCENTE["email"]]) == 0
    assert "Pedro Ruiz ahora es administrador" in capsys.readouterr().out
    assert gestionar_usuarios.main(["listar"]) == 0
    assert capsys.readouterr().out.count("Administrador") == 2


def test_script_email_inexistente(tmp_path, monkeypatch, capsys):
    """Con un email sin cuenta, el script avisa y termina con error."""
    monkeypatch.setenv("ASISTENCIA_BD", str(tmp_path / "script.db"))
    assert gestionar_usuarios.main(["hacer-admin",
                                    "nadie@escuela.edu.ar"]) == 1
    assert "No hay ninguna cuenta" in capsys.readouterr().out
