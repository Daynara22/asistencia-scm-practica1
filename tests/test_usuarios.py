"""Tests de cuentas de usuario y login (servicios/usuarios.py y
seguridad.py)."""
import pytest

from asistencia import seguridad
from asistencia.servicios import usuarios
from asistencia.validaciones import ErrorValidacion
from tests.conftest import DOCENTE


def registrar(conexion, **cambios):
    """Registra el docente de prueba, con los cambios indicados."""
    datos = {**DOCENTE, **cambios}
    return usuarios.registrar_docente(
        conexion, datos["email"], datos["nombre"], datos["apellido"],
        datos["clave"], datos["clave_repetida"])


# ---------------- Contraseñas ----------------

def test_hash_de_clave_se_verifica():
    """El hash no contiene la clave y solo la clave correcta lo
    verifica."""
    hash_guardado = seguridad.generar_hash_clave("Clave123!")
    assert hash_guardado.startswith("scrypt:")
    assert "Clave123!" not in hash_guardado
    assert seguridad.verificar_clave(hash_guardado, "Clave123!")
    assert not seguridad.verificar_clave(hash_guardado, "Clave1234!")


def test_hash_de_clave_usa_sal_distinta():
    """Dos hashes de la misma clave son distintos (sal aleatoria)."""
    assert seguridad.generar_hash_clave("Clave123!") != \
        seguridad.generar_hash_clave("Clave123!")


def test_hash_danado_no_rompe():
    """Un hash con formato desconocido no lanza error: no verifica."""
    assert not seguridad.verificar_clave("cualquier-cosa", "Clave123!")
    assert not seguridad.verificar_clave("md5$sal$abc", "Clave123!")


def test_acepta_hash_pbkdf2():
    """Se aceptan hashes pbkdf2 (formato de versiones anteriores)."""
    import hashlib
    resumen = hashlib.pbkdf2_hmac("sha256", b"Clave123!", b"sal",
                                  1000).hex()
    hash_guardado = f"pbkdf2:sha256:1000$sal${resumen}"
    assert seguridad.verificar_clave(hash_guardado, "Clave123!")


# ---------------- Registro ----------------

def test_registro_guarda_hash_y_no_la_clave(conexion):
    """En la base queda el hash, nunca la contraseña en texto plano."""
    usuario = registrar(conexion)
    fila = conexion.execute("SELECT * FROM usuarios").fetchone()
    assert fila["email"] == usuario.email == DOCENTE["email"]
    assert "Clave123!" not in fila["clave_hash"]
    assert usuario.nombre_completo == "María González"


def test_registro_email_repetido(conexion):
    """No puede haber dos cuentas con el mismo email (sin importar
    mayúsculas)."""
    registrar(conexion)
    with pytest.raises(ErrorValidacion, match="Ya existe una cuenta"):
        registrar(conexion, email="MARIA.Gonzalez@escuela.edu.ar")


def test_registro_con_datos_invalidos_no_guarda(conexion):
    """Si un dato es inválido, no se crea la cuenta."""
    with pytest.raises(ErrorValidacion):
        registrar(conexion, email="maria@")
    total = conexion.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    assert total == 0


# ---------------- Login ----------------

def test_login_correcto(conexion):
    """Con email y clave correctos devuelve el usuario."""
    creado = registrar(conexion)
    usuario = usuarios.autenticar(conexion, "  Maria.Gonzalez@escuela.edu.ar",
                                  "Clave123!")
    assert usuario.id == creado.id


@pytest.mark.parametrize("email, clave", [
    ("maria.gonzalez@escuela.edu.ar", "Incorrecta1!"),
    ("nadie@escuela.edu.ar", "Clave123!"),
])
def test_login_incorrecto_mismo_mensaje(conexion, email, clave):
    """Clave mal o email inexistente dan el mismo mensaje."""
    registrar(conexion)
    with pytest.raises(ErrorValidacion,
                       match="El email o la contraseña no son correctos"):
        usuarios.autenticar(conexion, email, clave)


def test_login_sin_datos(conexion):
    """Si falta el email o la clave, se pide completarlos."""
    with pytest.raises(ErrorValidacion, match="Ingresá tu email"):
        usuarios.autenticar(conexion, "", "")


def test_obtener_usuario(conexion):
    """Se busca un usuario por id; si no existe devuelve None."""
    creado = registrar(conexion)
    assert usuarios.obtener(conexion, creado.id).email == creado.email
    assert usuarios.obtener(conexion, 999) is None
