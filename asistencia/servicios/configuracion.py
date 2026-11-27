"""configuracion.py - Opciones del sistema (por ahora, la hora límite)."""
from asistencia.bd import transaccion
from asistencia.validaciones import validar_hora

HORA_LIMITE_POR_DEFECTO = "08:15"


def _leer(conexion, clave, por_defecto):
    """Devuelve el valor guardado de una opción, o el valor por defecto."""
    fila = conexion.execute(
        "SELECT valor FROM configuracion WHERE clave = ?",
        (clave,)).fetchone()
    return fila["valor"] if fila else por_defecto


def _guardar(conexion, clave, valor):
    """Guarda (o reemplaza) el valor de una opción."""
    with transaccion(conexion):
        conexion.execute(
            "INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
            "ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
            (clave, valor))


def texto_hora_limite(conexion):
    """La hora límite como texto 'HH:MM'."""
    return _leer(conexion, "hora_limite", HORA_LIMITE_POR_DEFECTO)


def obtener_hora_limite(conexion):
    """La hora límite como objeto time, para comparar."""
    return validar_hora(texto_hora_limite(conexion))


def cambiar_hora_limite(conexion, texto):
    """Cambia la hora límite. Devuelve la nueva hora como 'HH:MM'."""
    hora = validar_hora(texto).strftime("%H:%M")
    _guardar(conexion, "hora_limite", hora)
    return hora
