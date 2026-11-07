"""
datos.py - Lectura y escritura del archivo JSON.

Todo el sistema se guarda en un único archivo: datos/asistencia.json

Estructura del archivo:
{
  "config": {"hora_limite": "08:15"},
  "alumnos": {
    "45123456": {"nombre": "Juan", "apellido": "Pérez"}
  },
  "asistencias": {
    "2026-11-06": {
      "45123456": {"estado": "PRESENTE", "hora": "08:02", "manual": false}
    }
  },
  "dias_cerrados": ["2026-11-05"],
  "docentes": {
    "maria.gonzalez@escuela.edu.ar": {"nombre": "María", "apellido": "González", "clave": "<hash>"}
  }
}

La contraseña de cada docente nunca se guarda tal cual: se guarda un hash.
"""
import json
import os
import shutil
from datetime import datetime

CARPETA_BASE = os.path.dirname(os.path.abspath(__file__))
ARCHIVO = os.path.join(CARPETA_BASE, "datos", "asistencia.json")
HORA_LIMITE_POR_DEFECTO = "08:15"
ESTADOS_VALIDOS = ("PRESENTE", "TARDANZA", "AUSENTE")


def datos_vacios():
    """Devuelve la estructura inicial, sin alumnos ni asistencias."""
    return {
        "config": {"hora_limite": HORA_LIMITE_POR_DEFECTO},
        "alumnos": {},
        "asistencias": {},
        "dias_cerrados": [],
        "docentes": {},
    }


def _es_valido(datos):
    """Revisa que el contenido del JSON tenga la forma que espera el sistema."""
    if not isinstance(datos, dict):
        return False

    config = datos.get("config")
    if not isinstance(config, dict) or not isinstance(config.get("hora_limite"), str):
        return False
    try:
        datetime.strptime(config["hora_limite"], "%H:%M")
    except ValueError:
        return False

    alumnos = datos.get("alumnos")
    if not isinstance(alumnos, dict):
        return False
    for alumno in alumnos.values():
        if not isinstance(alumno, dict):
            return False
        if not isinstance(alumno.get("nombre"), str) or not isinstance(alumno.get("apellido"), str):
            return False

    asistencias = datos.get("asistencias")
    if not isinstance(asistencias, dict):
        return False
    for registros_del_dia in asistencias.values():
        if not isinstance(registros_del_dia, dict):
            return False
        for registro in registros_del_dia.values():
            if not isinstance(registro, dict) or registro.get("estado") not in ESTADOS_VALIDOS:
                return False

    cerrados = datos.get("dias_cerrados")
    if not isinstance(cerrados, list) or not all(isinstance(f, str) for f in cerrados):
        return False

    # "docentes" puede faltar en archivos creados antes de agregar el login.
    docentes = datos.get("docentes", {})
    if not isinstance(docentes, dict):
        return False
    for docente in docentes.values():
        if not isinstance(docente, dict):
            return False
        if not all(isinstance(docente.get(campo), str) for campo in ("nombre", "apellido", "clave")):
            return False

    return True


def _guardar_copia_danada(archivo):
    """Copia el archivo dañado con otro nombre para no perderlo. Devuelve la ruta o None."""
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    base, extension = os.path.splitext(archivo)
    copia = f"{base}.danado-{marca}{extension}"
    try:
        shutil.copy2(archivo, copia)
        return copia
    except OSError:
        return None


def cargar(archivo=None):
    """
    Lee el archivo JSON.
    Devuelve una tupla (datos, aviso):
      - aviso es None si todo salió bien.
      - aviso es un texto para mostrar en pantalla si el archivo estaba dañado.
    Nunca lanza excepciones: si algo falla, empieza con datos vacíos.
    """
    archivo = archivo or ARCHIVO

    if not os.path.exists(archivo):
        return datos_vacios(), None

    try:
        with open(archivo, "r", encoding="utf-8") as f:
            datos = json.load(f)
        if _es_valido(datos):
            datos.setdefault("docentes", {})   # archivos viejos, sin login
            return datos, None
    except (OSError, ValueError, RecursionError):
        # ValueError incluye json.JSONDecodeError y UnicodeDecodeError
        pass

    # Si llegamos acá, el archivo está dañado: copia de seguridad y datos nuevos.
    copia = _guardar_copia_danada(archivo)
    datos = datos_vacios()
    try:
        guardar(datos, archivo)
    except OSError:
        pass

    if copia:
        aviso = (f"El archivo de datos estaba dañado. Se guardó una copia en "
                 f"«{os.path.basename(copia)}» y el sistema siguió con datos vacíos.")
    else:
        aviso = ("El archivo de datos estaba dañado y no se pudo hacer una copia. "
                 "El sistema siguió con datos vacíos.")
    return datos, aviso


def guardar(datos, archivo=None):
    """
    Guarda los datos en el JSON de forma segura:
    primero escribe un archivo temporal y después lo reemplaza,
    así un corte de luz no deja el archivo a medio escribir.
    Puede lanzar OSError si no hay permisos o espacio en disco.
    """
    archivo = archivo or ARCHIVO
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    temporal = archivo + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(temporal, archivo)
