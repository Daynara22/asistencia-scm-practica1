"""
migracion.py - Importa los datos del antiguo archivo JSON a SQLite.

Hasta la versión con SQLite, todo se guardaba en datos/asistencia.json:
{
  "config": {"hora_limite": "08:15"},
  "alumnos": {"45123456": {"nombre": "Juan", "apellido": "Pérez"}},
  "asistencias": {
    "2026-11-06": {
      "45123456": {"estado": "PRESENTE", "hora": "08:02", "manual": false}
    }
  },
  "dias_cerrados": ["2026-11-05"],
  "docentes": {
    "maria@escuela.edu.ar": {"nombre": "María", "apellido": "González",
                             "clave": "<hash>"}
  }
}

La importación se puede repetir sin duplicar nada: lo que ya existe en la
base (mismo DNI, mismo email o mismo alumno y fecha) se saltea. El
archivo JSON no se modifica.
"""
import json
from datetime import datetime

from asistencia.bd import transaccion
from asistencia.modelos import ESTADOS


class ErrorMigracion(Exception):
    """El archivo JSON no se puede leer o no tiene la forma esperada."""


def _es_texto(valor):
    """True si el valor es un string."""
    return isinstance(valor, str)


def _validar_estructura(datos):
    """Lanza ErrorMigracion si el contenido no tiene la forma esperada."""
    if not isinstance(datos, dict):
        raise ErrorMigracion("El archivo no contiene un objeto JSON.")

    hora = datos.get("config", {}).get("hora_limite")
    try:
        datetime.strptime(hora, "%H:%M")
    except (TypeError, ValueError):
        raise ErrorMigracion("La hora límite no es válida.")

    for dni, alumno in datos.get("alumnos", {}).items():
        if not (isinstance(alumno, dict) and _es_texto(alumno.get("nombre"))
                and _es_texto(alumno.get("apellido"))):
            raise ErrorMigracion(f"El alumno {dni} no tiene nombre y "
                                 "apellido.")

    for fecha, registros in datos.get("asistencias", {}).items():
        for dni, registro in registros.items():
            if registro.get("estado") not in ESTADOS:
                raise ErrorMigracion(
                    f"El registro de {dni} el {fecha} tiene un estado "
                    "inválido.")

    for email, docente in datos.get("docentes", {}).items():
        campos = ("nombre", "apellido", "clave")
        if not all(_es_texto(docente.get(campo)) for campo in campos):
            raise ErrorMigracion(f"Faltan datos del docente {email}.")


def leer_json(ruta):
    """Lee y valida el archivo JSON. Devuelve su contenido."""
    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError) as error:
        raise ErrorMigracion(f"No se pudo leer el archivo: {error}")
    try:
        _validar_estructura(datos)
    except (AttributeError, TypeError):
        # Por ejemplo, "alumnos" es una lista en lugar de un objeto.
        raise ErrorMigracion("El archivo no tiene la forma esperada.")
    return datos


def importar(conexion, datos):
    """
    Copia los datos del JSON a la base.

    Devuelve un diccionario con cuántos elementos se importaron de cada
    tipo (los que ya existían no se cuentan).
    """
    resultado = {"alumnos": 0, "asistencias": 0, "dias_cerrados": 0,
                 "docentes": 0}

    def insertar(tabla, sql, valores):
        """Ejecuta un INSERT OR IGNORE y suma si agregó una fila."""
        cursor = conexion.execute(sql, valores)
        resultado[tabla] += cursor.rowcount

    with transaccion(conexion):
        conexion.execute(
            "INSERT INTO configuracion (clave, valor) "
            "VALUES ('hora_limite', ?) "
            "ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
            (datos["config"]["hora_limite"],))

        for dni, alumno in datos.get("alumnos", {}).items():
            insertar("alumnos",
                     "INSERT OR IGNORE INTO alumnos (dni, nombre, apellido) "
                     "VALUES (?, ?, ?)",
                     (dni, alumno["nombre"], alumno["apellido"]))

        ids = {fila["dni"]: fila["id"] for fila in
               conexion.execute("SELECT id, dni FROM alumnos")}
        for fecha, registros in datos.get("asistencias", {}).items():
            for dni, registro in registros.items():
                if dni not in ids:
                    continue    # registro de un alumno que ya no existe
                insertar("asistencias",
                         "INSERT OR IGNORE INTO asistencias "
                         "(alumno_id, fecha, estado, hora, manual) "
                         "VALUES (?, ?, ?, ?, ?)",
                         (ids[dni], fecha, registro["estado"],
                          registro.get("hora"),
                          int(bool(registro.get("manual")))))

        for fecha in datos.get("dias_cerrados", []):
            insertar("dias_cerrados",
                     "INSERT OR IGNORE INTO dias_cerrados (fecha) "
                     "VALUES (?)", (fecha,))

        for email, docente in datos.get("docentes", {}).items():
            insertar("docentes",
                     "INSERT OR IGNORE INTO usuarios "
                     "(email, nombre, apellido, clave_hash) "
                     "VALUES (?, ?, ?, ?)",
                     (email.lower(), docente["nombre"], docente["apellido"],
                      docente["clave"]))
    return resultado
