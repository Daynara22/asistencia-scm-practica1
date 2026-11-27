"""
gestionar_usuarios.py - Tareas de cuentas de usuario desde la terminal.

Uso:
    python gestionar_usuarios.py listar
    python gestionar_usuarios.py hacer-admin EMAIL

"hacer-admin" sirve, por ejemplo, después de migrar los datos del JSON:
todas las cuentas migradas quedan como docentes y así se elige quién
administra el sistema.
"""
import argparse
import sys
from contextlib import closing

from asistencia import bd
from asistencia.servicios import usuarios
from asistencia.validaciones import ErrorValidacion


def armar_parser():
    """Define los comandos y argumentos del script."""
    parser = argparse.ArgumentParser(
        description="Gestión de cuentas del Sistema de Asistencia.")
    comandos = parser.add_subparsers(dest="comando", required=True)
    comandos.add_parser("listar", help="Muestra todas las cuentas.")
    admin = comandos.add_parser("hacer-admin",
                                help="Da el rol de administrador.")
    admin.add_argument("email", help="Email de la cuenta.")
    return parser


def main(argumentos):
    """Ejecuta el comando pedido. Devuelve el código de salida (0 =
    bien)."""
    opciones = armar_parser().parse_args(argumentos)
    with closing(bd.conectar()) as conexion:
        if opciones.comando == "listar":
            for cuenta in usuarios.listar(conexion):
                print(f"{cuenta['email']:<40} {cuenta['nombre_rol']:<14} "
                      f"{cuenta['nombre']} {cuenta['apellido']}")
            return 0
        try:
            usuario = usuarios.hacer_administrador(conexion, opciones.email)
        except ErrorValidacion as error:
            print(error)
            return 1
        print(f"{usuario.nombre_completo} ahora es administrador.")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
