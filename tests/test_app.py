"""Tests de las pantallas web: que respondan y que validen en el servidor."""
import pytest
from fastapi.testclient import TestClient

import app as aplicacion
import datos as almacen


DOCENTE = {
    "email": "maria.gonzalez@escuela.edu.ar",
    "nombre": "María",
    "apellido": "González",
    "clave": "Clave123!",
    "clave_repetida": "Clave123!",
}


@pytest.fixture
def anonimo(tmp_path, monkeypatch):
    """Cliente sin sesión iniciada. Cada test usa su propio archivo JSON temporal."""
    monkeypatch.setattr(almacen, "ARCHIVO", str(tmp_path / "datos" / "asistencia.json"))
    # follow_redirects=False: así los tests pueden revisar las redirecciones (302).
    return TestClient(aplicacion.app, follow_redirects=False)


@pytest.fixture
def cliente(anonimo):
    """Cliente con un docente registrado y con la sesión iniciada."""
    anonimo.post("/registro-docente", data=DOCENTE)
    return anonimo


def texto(respuesta):
    return respuesta.text


@pytest.mark.parametrize("ruta", ["/", "/asistencia", "/alumnos", "/informe"])
def test_paginas_abren(cliente, ruta):
    assert cliente.get(ruta).status_code == 200


def test_flujo_completo(cliente):
    r = cliente.post("/alumnos", data={"dni": "45123456", "nombre": "Juan", "apellido": "Pérez"}, follow_redirects=True)
    assert "Se dio de alta a Juan Pérez" in texto(r)

    r = cliente.post("/registrar", data={"dni": "45123456"}, follow_redirects=True)
    assert "Juan Pérez" in texto(r)
    assert "resultado-presente" in texto(r) or "resultado-tardanza" in texto(r)

    r = cliente.post("/cerrar-dia", follow_redirects=True)
    assert "Día cerrado" in texto(r)

    r = cliente.get("/informe?dni=45123456")
    assert "Juan Pérez" in texto(r) and "100.0 %" in texto(r)


def test_validacion_en_servidor(cliente):
    r = cliente.post("/alumnos", data={"dni": "12ab", "nombre": "", "apellido": "X"})
    assert r.status_code == 400
    assert "El DNI solo puede tener números" in texto(r)


def test_dni_inexistente_muestra_mensaje(cliente):
    r = cliente.post("/registrar", data={"dni": "99999999"})
    assert r.status_code == 400 and "No hay ningún alumno" in texto(r)


def test_formulario_sin_campos_no_rompe(cliente):
    for ruta in ["/registrar", "/manual", "/hora-limite", "/alumnos"]:
        assert cliente.post(ruta, data={}).status_code == 400


def test_json_danado_muestra_aviso(anonimo, tmp_path):
    (tmp_path / "datos").mkdir()
    (tmp_path / "datos" / "asistencia.json").write_text("{roto", encoding="utf-8")
    r = anonimo.get("/login")
    assert r.status_code == 200 and "dañado" in texto(r)


def test_pagina_inexistente(cliente):
    r = cliente.get("/no-existe")
    assert r.status_code == 404 and "no existe" in texto(r)


# ----------------------------------------------------------------------
# Login de docentes
# ----------------------------------------------------------------------

@pytest.mark.parametrize("ruta", ["/", "/asistencia", "/alumnos", "/informe"])
def test_sin_login_redirige_al_login(anonimo, ruta):
    r = anonimo.get(ruta)
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")


def test_sin_login_no_se_puede_registrar_asistencia(anonimo):
    r = anonimo.post("/registrar", data={"dni": "45123456"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")


@pytest.mark.parametrize("ruta", ["/login", "/registro-docente"])
def test_paginas_de_acceso_abren_sin_login(anonimo, ruta):
    r = anonimo.get(ruta)
    assert r.status_code == 200 and "pagina-acceso" in texto(r)


def test_registro_saluda_al_docente_por_su_nombre(anonimo):
    r = anonimo.post("/registro-docente", data=DOCENTE, follow_redirects=True)
    assert "Bienvenido docente" in texto(r) and "María González" in texto(r)


def test_login_correcto_detecta_al_docente(anonimo):
    anonimo.post("/registro-docente", data=DOCENTE)
    anonimo.post("/logout")
    otro = {**DOCENTE, "email": "pedro.ruiz@escuela.edu.ar", "nombre": "Pedro", "apellido": "Ruiz"}
    anonimo.post("/registro-docente", data=otro)
    anonimo.post("/logout")

    r = anonimo.post("/login", data={"email": "  Pedro.Ruiz@Escuela.edu.ar ", "clave": "Clave123!"},
                     follow_redirects=True)
    assert "Bienvenido docente" in texto(r) and "Pedro Ruiz" in texto(r)
    assert "María González" not in texto(r)


@pytest.mark.parametrize("email, clave", [
    ("maria.gonzalez@escuela.edu.ar", "Incorrecta1!"),
    ("nadie@escuela.edu.ar", "Clave123!"),
])
def test_login_incorrecto(cliente, email, clave):
    cliente.post("/logout")
    r = cliente.post("/login", data={"email": email, "clave": clave})
    assert r.status_code == 400 and "El email o la contraseña no son correctos" in texto(r)
    assert cliente.get("/").status_code == 302


def test_logout_cierra_la_sesion(cliente):
    r = cliente.post("/logout", follow_redirects=True)
    assert "Cerraste la sesión" in texto(r)
    assert cliente.get("/").status_code == 302


def test_la_clave_no_se_guarda_tal_cual(cliente, tmp_path):
    contenido = (tmp_path / "datos" / "asistencia.json").read_text(encoding="utf-8")
    assert "maria.gonzalez@escuela.edu.ar" in contenido
    assert "Clave123!" not in contenido


@pytest.mark.parametrize("clave, mensaje", [
    ("Ab1!", "al menos 8 caracteres"),
    ("12345678!", "al menos una letra"),
    ("Abcdefgh!", "al menos un número"),
    ("Abcdefg12", "al menos un carácter especial"),
])
def test_registro_exige_clave_segura(anonimo, clave, mensaje):
    r = anonimo.post("/registro-docente", data={**DOCENTE, "clave": clave, "clave_repetida": clave})
    assert r.status_code == 400 and mensaje in texto(r)


def test_registro_claves_distintas(anonimo):
    r = anonimo.post("/registro-docente", data={**DOCENTE, "clave_repetida": "Otra123!"})
    assert r.status_code == 400 and "no coinciden" in texto(r)


def test_registro_email_repetido(cliente):
    cliente.post("/logout")
    r = cliente.post("/registro-docente", data=DOCENTE)
    assert r.status_code == 400 and "Ya existe una cuenta" in texto(r)


def test_registro_email_invalido(anonimo):
    r = anonimo.post("/registro-docente", data={**DOCENTE, "email": "maria@"})
    assert r.status_code == 400 and "El email no es válido" in texto(r)


def test_envio_demasiado_grande(cliente):
    r = cliente.post("/alumnos", data={"nombre": "x" * 20000})
    assert r.status_code == 413 and "demasiado grandes" in texto(r)


# ----------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------

def test_login_lleva_al_dashboard(anonimo):
    r = anonimo.post("/registro-docente", data=DOCENTE)
    assert r.status_code == 302 and r.headers["Location"] == "/"
    r = anonimo.get("/")
    assert "Dashboard" in texto(r) and "Bienvenido docente" in texto(r)


def test_dashboard_vacio(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "Todavía no hay asistencias registradas" in texto(r)


def test_dashboard_muestra_grafico_y_ranking(cliente):
    cliente.post("/alumnos", data={"dni": "45123456", "nombre": "Juan", "apellido": "Pérez"})
    cliente.post("/alumnos", data={"dni": "40111222", "nombre": "Ana", "apellido": "Díaz"})
    cliente.post("/registrar", data={"dni": "45123456"})
    cliente.post("/cerrar-dia")      # Ana queda AUSENTE

    r = cliente.get("/")
    pagina = texto(r)
    assert 'id="grafico-dias"' in pagina
    assert "Más ausencias" in pagina and "Ana Díaz" in pagina
    assert "Asistencia general: <strong>50.0 %</strong>" in pagina
