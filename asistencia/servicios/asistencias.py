"""
asistencias.py - Registro de asistencia, carga manual y cierre del día.

Reglas:
- Hasta la hora límite (inclusive) el alumno queda PRESENTE; después,
  TARDANZA.
- Cada alumno tiene como máximo un registro por fecha.
- Al cerrar el día se marca AUSENTE a quien no se registró y el día ya no
  admite más registros.
"""
import sqlite3
from datetime import date, datetime, time

from asistencia.bd import transaccion
from asistencia.modelos import AUSENTE, PRESENTE, TARDANZA
from asistencia.servicios import alumnos
from asistencia.servicios.configuracion import obtener_hora_limite
from asistencia.validaciones import (ErrorValidacion, validar_fecha,
                                     validar_hora)


def calcular_estado(hora_llegada, hora_limite):
    """PRESENTE si llegó hasta la hora límite (inclusive), TARDANZA si
    llegó después."""
    return PRESENTE if hora_llegada <= hora_limite else TARDANZA


def dia_cerrado(conexion, fecha):
    """True si el día ya fue cerrado."""
    fila = conexion.execute(
        "SELECT 1 FROM dias_cerrados WHERE fecha = ?",
        (fecha.isoformat(),)).fetchone()
    return fila is not None


def _registro_previo(conexion, alumno_id, fecha):
    """Devuelve el registro del alumno en esa fecha, o None."""
    return conexion.execute(
        "SELECT estado, hora FROM asistencias "
        "WHERE alumno_id = ? AND fecha = ?",
        (alumno_id, fecha.isoformat())).fetchone()


def _insertar(conexion, alumno_id, fecha, estado, hora, manual):
    """Guarda un registro de asistencia."""
    conexion.execute(
        "INSERT INTO asistencias (alumno_id, fecha, estado, hora, manual) "
        "VALUES (?, ?, ?, ?, ?)",
        (alumno_id, fecha.isoformat(), estado, hora, int(manual)))


def registrar(conexion, dni, ahora=None):
    """
    Registra la llegada de un alumno con la hora actual.

    El estado (PRESENTE o TARDANZA) se calcula solo según la hora límite.
    Devuelve un diccionario con nombre, dni, estado, hora y manual.
    """
    ahora = ahora or datetime.now()
    hoy = ahora.date()
    alumno = alumnos.buscar_por_dni(conexion, dni)
    hora_llegada = time(ahora.hour, ahora.minute)

    try:
        with transaccion(conexion):
            if dia_cerrado(conexion, hoy):
                raise ErrorValidacion(
                    "El día de hoy ya está cerrado: no se pueden registrar "
                    "más asistencias.")
            previo = _registro_previo(conexion, alumno.id, hoy)
            if previo:
                detalle = f" a las {previo['hora']}" if previo["hora"] else ""
                raise ErrorValidacion(
                    f"{alumno.nombre_completo} ya tiene registrada la "
                    f"asistencia de hoy ({previo['estado']}{detalle}).")
            estado = calcular_estado(hora_llegada,
                                     obtener_hora_limite(conexion))
            hora = hora_llegada.strftime("%H:%M")
            _insertar(conexion, alumno.id, hoy, estado, hora, manual=False)
    except sqlite3.IntegrityError:
        # Dos registros del mismo alumno exactamente al mismo tiempo.
        raise ErrorValidacion(
            f"{alumno.nombre_completo} ya tiene registrada la asistencia "
            "de hoy.")

    return {"nombre": alumno.nombre_completo, "dni": alumno.dni,
            "estado": estado, "hora": hora, "manual": False}


def carga_manual(conexion, dni, fecha_texto, estado, hora_texto=None,
                 hoy=None):
    """
    Carga a mano una TARDANZA o una AUSENCIA (por ejemplo, de otro día).

    - TARDANZA: pide la hora de llegada, que debe ser posterior a la hora
      límite.
    - AUSENTE: no lleva hora.
    """
    hoy = hoy or date.today()
    alumno = alumnos.buscar_por_dni(conexion, dni)
    fecha = validar_fecha(fecha_texto)

    if fecha > hoy:
        raise ErrorValidacion(
            "No se puede cargar asistencia de una fecha futura.")

    estado = str(estado or "").strip().upper()
    if estado not in (TARDANZA, AUSENTE):
        raise ErrorValidacion(
            "En la carga manual el estado debe ser TARDANZA o AUSENTE.")

    hora = None
    if estado == TARDANZA:
        if not str(hora_texto or "").strip():
            raise ErrorValidacion(
                "Para cargar una tardanza ingresá la hora de llegada.")
        hora_llegada = validar_hora(hora_texto)
        limite = obtener_hora_limite(conexion)
        if hora_llegada <= limite:
            raise ErrorValidacion(
                f"A las {hora_llegada.strftime('%H:%M')} no es tardanza: "
                f"la hora límite es {limite.strftime('%H:%M')}.")
        hora = hora_llegada.strftime("%H:%M")

    mensaje_repetido = (f"{alumno.nombre_completo} ya tiene un registro "
                        f"el {fecha.strftime('%d/%m/%Y')}")
    try:
        with transaccion(conexion):
            previo = _registro_previo(conexion, alumno.id, fecha)
            if previo:
                raise ErrorValidacion(
                    f"{mensaje_repetido} ({previo['estado']}).")
            _insertar(conexion, alumno.id, fecha, estado, hora, manual=True)
    except sqlite3.IntegrityError:
        raise ErrorValidacion(f"{mensaje_repetido}.")

    return {"nombre": alumno.nombre_completo, "dni": alumno.dni,
            "fecha": fecha.isoformat(), "estado": estado, "hora": hora,
            "manual": True}


def cerrar_dia(conexion, hoy=None):
    """
    Marca AUSENTE a quienes no registraron asistencia y bloquea el día.

    Devuelve cuántos alumnos quedaron marcados como ausentes.
    """
    hoy = hoy or date.today()
    with transaccion(conexion):
        if dia_cerrado(conexion, hoy):
            raise ErrorValidacion("El día de hoy ya estaba cerrado.")
        cursor = conexion.execute(
            "INSERT INTO asistencias (alumno_id, fecha, estado, hora, manual)"
            " SELECT id, ?, ?, NULL, 0 FROM alumnos WHERE id NOT IN "
            "(SELECT alumno_id FROM asistencias WHERE fecha = ?)",
            (hoy.isoformat(), AUSENTE, hoy.isoformat()))
        conexion.execute("INSERT INTO dias_cerrados (fecha) VALUES (?)",
                         (hoy.isoformat(),))
    return cursor.rowcount


def resumen_del_dia(conexion, hoy=None):
    """Cantidades del día y la lista de registros, para la pantalla de
    registro."""
    hoy = hoy or date.today()
    filas = conexion.execute(
        "SELECT al.dni, al.nombre || ' ' || al.apellido AS nombre, "
        "a.estado, a.hora, a.manual "
        "FROM asistencias a JOIN alumnos al ON al.id = a.alumno_id "
        "WHERE a.fecha = ?", (hoy.isoformat(),)).fetchall()

    cantidades = {PRESENTE: 0, TARDANZA: 0, AUSENTE: 0}
    registros = []
    for fila in filas:
        cantidades[fila["estado"]] += 1
        registros.append({**dict(fila), "manual": bool(fila["manual"])})
    # Primero los que llegaron (por hora), al final los ausentes.
    registros.sort(key=lambda r: (r["hora"] is None, r["hora"] or "",
                                  r["nombre"]))
    sin_registrar = alumnos.cantidad(conexion) - len(filas)
    return {"cantidades": cantidades, "sin_registrar": sin_registrar,
            "registros": registros}
