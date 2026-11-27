"""
usuarios.py - Cuentas para entrar al sistema, roles y login.

Reglas:
- El primer usuario que se registra en una base vacía queda como
  administrador; los siguientes, como docentes.
- Las cuentas de alumno las crea un administrador y quedan vinculadas a
  un alumno ya dado de alta (una cuenta por alumno).
- Siempre tiene que quedar al menos un administrador.
"""
import sqlite3

from asistencia.bd import transaccion
from asistencia.modelos import ADMINISTRADOR, ALUMNO, DOCENTE, Usuario
from asistencia.seguridad import generar_hash_clave, verificar_clave
from asistencia.servicios import alumnos
from asistencia.validaciones import (ErrorValidacion, validar_clave,
                                     validar_email, validar_nombre)

MENSAJE_EMAIL_REPETIDO = "Ya existe una cuenta con ese email."
NOMBRES_DE_ROL = {ADMINISTRADOR: "Administrador", DOCENTE: "Docente",
                  ALUMNO: "Alumno"}


def _insertar(conexion, email, nombre, apellido, clave_hash, rol,
              alumno_id=None):
    """Guarda la cuenta y devuelve su id. El email no puede repetirse."""
    try:
        cursor = conexion.execute(
            "INSERT INTO usuarios "
            "(email, nombre, apellido, clave_hash, rol, alumno_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (email, nombre, apellido, clave_hash, rol, alumno_id))
    except sqlite3.IntegrityError:
        # La columna email es UNIQUE: así no se crean dos cuentas iguales
        # aunque dos personas se registren en el mismo instante.
        raise ErrorValidacion(MENSAJE_EMAIL_REPETIDO)
    return cursor.lastrowid


def registrar_docente(conexion, email, nombre, apellido, clave, repetida):
    """
    Crea la cuenta de un docente y la devuelve.

    Si es la primera cuenta del sistema, queda como administrador.
    La contraseña se guarda como hash, nunca tal cual.
    """
    email = validar_email(email)
    nombre = validar_nombre(nombre, "nombre")
    apellido = validar_nombre(apellido, "apellido")
    clave = validar_clave(clave, repetida)
    clave_hash = generar_hash_clave(clave)

    with transaccion(conexion):
        # Se cuenta dentro de la transacción: si dos personas se registran
        # a la vez en una base vacía, solo una queda como administrador.
        hay_usuarios = conexion.execute(
            "SELECT 1 FROM usuarios LIMIT 1").fetchone()
        rol = DOCENTE if hay_usuarios else ADMINISTRADOR
        usuario_id = _insertar(conexion, email, nombre, apellido,
                               clave_hash, rol)
    return Usuario(usuario_id, email, nombre, apellido, clave_hash, rol)


def crear_cuenta_alumno(conexion, dni, email, clave, repetida):
    """
    Crea la cuenta para que un alumno vea su propia asistencia.

    El alumno ya tiene que estar dado de alta; el nombre se toma de ahí.
    """
    alumno = alumnos.buscar_por_dni(conexion, dni)
    email = validar_email(email)
    clave = validar_clave(clave, repetida)
    clave_hash = generar_hash_clave(clave)

    with transaccion(conexion):
        tiene_cuenta = conexion.execute(
            "SELECT 1 FROM usuarios WHERE alumno_id = ?",
            (alumno.id,)).fetchone()
        if tiene_cuenta:
            raise ErrorValidacion(
                f"{alumno.nombre_completo} ya tiene una cuenta.")
        usuario_id = _insertar(conexion, email, alumno.nombre,
                               alumno.apellido, clave_hash, ALUMNO,
                               alumno.id)
    return Usuario(usuario_id, email, alumno.nombre, alumno.apellido,
                   clave_hash, ALUMNO, alumno.id)


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


def listar(conexion):
    """
    Todas las cuentas, para la pantalla de usuarios.

    Cada elemento es un diccionario con los datos de la cuenta (sin el
    hash de la clave) y el DNI del alumno si es una cuenta de alumno.
    """
    filas = conexion.execute(
        "SELECT u.id, u.email, u.nombre, u.apellido, u.rol, "
        "al.dni AS alumno_dni "
        "FROM usuarios u LEFT JOIN alumnos al ON al.id = u.alumno_id "
        "ORDER BY u.apellido, u.nombre").fetchall()
    return [{**dict(fila), "nombre_rol": NOMBRES_DE_ROL[fila["rol"]]}
            for fila in filas]


def cambiar_rol(conexion, usuario_id, rol_nuevo):
    """
    Pasa una cuenta de docente a administrador o al revés.

    Las cuentas de alumno no cambian de rol, y no se puede quitar el rol
    al último administrador. Devuelve el usuario actualizado.
    """
    if rol_nuevo not in (ADMINISTRADOR, DOCENTE):
        raise ErrorValidacion("El rol debe ser administrador o docente.")
    try:
        usuario_id = int(usuario_id)
    except (TypeError, ValueError):
        raise ErrorValidacion("La cuenta indicada no existe.")

    with transaccion(conexion):
        usuario = obtener(conexion, usuario_id)
        if usuario is None:
            raise ErrorValidacion("La cuenta indicada no existe.")
        if usuario.es_alumno:
            raise ErrorValidacion(
                "Las cuentas de alumno no pueden cambiar de rol.")
        if usuario.es_administrador and rol_nuevo != ADMINISTRADOR:
            administradores = conexion.execute(
                "SELECT COUNT(*) FROM usuarios WHERE rol = ?",
                (ADMINISTRADOR,)).fetchone()[0]
            if administradores == 1:
                raise ErrorValidacion(
                    "Tiene que quedar al menos un administrador.")
        conexion.execute("UPDATE usuarios SET rol = ? WHERE id = ?",
                         (rol_nuevo, usuario_id))
    usuario.rol = rol_nuevo
    return usuario


def hacer_administrador(conexion, email):
    """Da el rol de administrador a la cuenta con ese email (para el
    script gestionar_usuarios.py)."""
    email = validar_email(email)
    fila = conexion.execute(
        "SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
    if fila is None:
        raise ErrorValidacion(f"No hay ninguna cuenta con el email {email}.")
    return cambiar_rol(conexion, fila["id"], ADMINISTRADOR)
