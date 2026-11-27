"""
migrar_json.py - Pasa los datos de datos/asistencia.json a la base SQLite.

Uso:
    python migrar_json.py [archivo.json]

Si no se indica el archivo, usa datos/asistencia.json. El JSON no se
modifica, así que queda como respaldo. Se puede ejecutar más de una vez:
lo que ya está en la base no se duplica.
"""
import os
import sys
from contextlib import closing

from asistencia import bd
from asistencia.migracion import ErrorMigracion, importar, leer_json

JSON_POR_DEFECTO = os.path.join(bd.CARPETA_BASE, "datos", "asistencia.json")


def main(argumentos):
    """Ejecuta la migración. Devuelve el código de salida (0 = bien)."""
    ruta_json = argumentos[0] if argumentos else JSON_POR_DEFECTO
    if not os.path.exists(ruta_json):
        print(f"No se encontró el archivo {ruta_json}.")
        return 1
    try:
        datos = leer_json(ruta_json)
    except ErrorMigracion as error:
        print(f"No se pudo migrar: {error}")
        return 1

    with closing(bd.conectar()) as conexion:
        resultado = importar(conexion, datos)

    print(f"Datos importados a {bd.ruta_configurada()}:")
    for tipo, cantidad in resultado.items():
        print(f"  {tipo}: {cantidad}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
