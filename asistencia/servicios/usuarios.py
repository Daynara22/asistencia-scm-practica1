"""usuarios.py - Cuentas para entrar al sistema y login."""
import sqlite3

from asistencia.bd import transaccion
from asistencia.modelos import Usuario
from asistencia.seguridad import generar_hash_clave, verificar_clave
from asistencia.validaciones import (ErrorValidacion, validar_clave,
                                     validar_email, validar_nombre)

MENSAJE_EMAIL_REPETIDO = "Ya existe una cuenta de docente con ese email."


def registrar_docente(conexion, email, nombre, apellido, clave, repetida):
    """
    Crea la cuenta de un docente y la devuelve.

    La contraseña se guarda como hash, nunca tal cual.
    """
    email = validar_email(email)
    nombre = validar_nombre(nombre, "nombre")
    apellido = validar_nombre(apellido, "apellido")
    clave = validar_clave(clave, repetida)
    clave_hash = generar_hash_clave(clave)

    try:
        with transaccion(conexion):
            cursor = conexion.execute(
                "INSERT INTO usuarios (email, nombre, apellido, clave_hash) "
                "VALUES (?, ?, ?, ?)",
                (email, nombre, apellido, clave_hash))
    except sqlite3.IntegrityError:
        # La columna email es UNIQUE: así no se crean dos cuentas iguales
        # aunque dos personas se registren en el mismo instante.
        raise ErrorValidacion(MENSAJE_EMAIL_REPETIDO)
    return Usuario(cursor.lastrowid, email, nombre, apellido, clave_hash)


def autenticar(conexion, email, clave):
    """
    Revisa email y contraseña y devuelve el usuario si son correctos.

    El mensaje de error es el mismo en todos los casos, para no revelar
    qué emails tienen cuenta.
    """
    email = str(email or "").strip().lower()
    clave = str(clave or "")
    if not email or not clave:
        raise ErrorValidacion("Ingresá tu email y tu contraseña.")

    fila = conexion.execute(
        "SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()
    if fila is None or not verificar_clave(fila["clave_hash"], clave):
        raise ErrorValidacion("El email o la contraseña no son correctos.")
    return Usuario.desde_fila(fila)


def obtener(conexion, usuario_id):
    """Devuelve el usuario con ese id, o None si no existe."""
    fila = conexion.execute(
        "SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    return Usuario.desde_fila(fila) if fila else None
