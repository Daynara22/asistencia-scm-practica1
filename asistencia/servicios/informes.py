"""
informes.py - Informe por alumno y resumen general para el dashboard.

El porcentaje de asistencia cuenta PRESENTE y TARDANZA como asistió
(el alumno vino, aunque tarde).
"""
from datetime import date, datetime

from asistencia.modelos import AUSENTE, PRESENTE, TARDANZA
from asistencia.servicios import alumnos, limites
from asistencia.servicios.asistencias import resumen_del_dia

DIAS_SEMANA = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


def porcentaje(parte, total):
    """Porcentaje con un decimal. Si el total es 0 devuelve 0.0."""
    return round(parte * 100 / total, 1) if total else 0.0


def _contar(filas):
    """Cuenta cuántas filas hay de cada estado."""
    cuenta = {PRESENTE: 0, TARDANZA: 0, AUSENTE: 0}
    for fila in filas:
        cuenta[fila["estado"]] += 1
    return cuenta


def _fecha_para_mostrar(texto):
    """'2026-11-06' -> '06/11/2026'."""
    return datetime.strptime(texto, "%Y-%m-%d").strftime("%d/%m/%Y")


def informe_alumno(conexion, dni):
    """Informe completo de un alumno: cantidades, porcentajes y detalle."""
    alumno = alumnos.buscar_por_dni(conexion, dni)
    filas = conexion.execute(
        "SELECT fecha, estado, hora, manual FROM asistencias "
        "WHERE alumno_id = ? ORDER BY fecha DESC", (alumno.id,)).fetchall()

    detalle = [{
        "fecha": fila["fecha"],
        "fecha_mostrar": _fecha_para_mostrar(fila["fecha"]),
        "estado": fila["estado"],
        "hora": fila["hora"],
        "manual": bool(fila["manual"]),
    } for fila in filas]

    cuenta = _contar(filas)
    total = len(filas)
    return {
        "dni": alumno.dni,
        "nombre": alumno.nombre_completo,
        "presentes": cuenta[PRESENTE],
        "tardanzas": cuenta[TARDANZA],
        "ausentes": cuenta[AUSENTE],
        "total": total,
        "porcentaje_asistencia": porcentaje(
            cuenta[PRESENTE] + cuenta[TARDANZA], total),
        "porcentaje_presentes": porcentaje(cuenta[PRESENTE], total),
        "porcentaje_tardanzas": porcentaje(cuenta[TARDANZA], total),
        "porcentaje_ausentes": porcentaje(cuenta[AUSENTE], total),
        "detalle": detalle,
        # Faltas, límite y estado (normal, cerca o superado).
        "situacion": limites.situacion_alumno(conexion, alumno),
    }


def porcentajes_por_alumno(conexion):
    """
    Porcentaje de asistencia de cada alumno, en una sola consulta.

    Devuelve {alumno_id: porcentaje}. Los alumnos sin registros no
    aparecen.
    """
    filas = conexion.execute(
        "SELECT alumno_id, COUNT(*) AS total, "
        "SUM(estado != 'AUSENTE') AS asistio "
        "FROM asistencias GROUP BY alumno_id")
    return {fila["alumno_id"]: porcentaje(fila["asistio"], fila["total"])
            for fila in filas}


def _dias_recientes(conexion, hoy, cantidad_dias):
    """Los últimos días con registros (hasta hoy), para el gráfico."""
    fechas = [fila["fecha"] for fila in conexion.execute(
        "SELECT DISTINCT fecha FROM asistencias WHERE fecha <= ? "
        "ORDER BY fecha DESC LIMIT ?", (hoy.isoformat(), cantidad_dias))]
    dias = []
    for texto in reversed(fechas):
        fecha = datetime.strptime(texto, "%Y-%m-%d").date()
        cuenta = _contar(conexion.execute(
            "SELECT estado FROM asistencias WHERE fecha = ?", (texto,)))
        dias.append({
            "fecha": texto,
            "etiqueta": (f"{DIAS_SEMANA[fecha.weekday()]} "
                         f"{fecha.strftime('%d/%m')}"),
            "fecha_mostrar": fecha.strftime("%d/%m/%Y"),
            "presentes": cuenta[PRESENTE],
            "tardanzas": cuenta[TARDANZA],
            "ausentes": cuenta[AUSENTE],
            "total": sum(cuenta.values()),
        })
    return dias


def _ranking(conexion, estado, cantidad):
    """Los alumnos con más registros del estado indicado."""
    filas = conexion.execute(
        "SELECT al.dni, al.nombre || ' ' || al.apellido AS nombre, "
        "COUNT(*) AS cantidad "
        "FROM asistencias a JOIN alumnos al ON al.id = a.alumno_id "
        "WHERE a.estado = ? GROUP BY al.id", (estado,)).fetchall()
    lista = [dict(fila) for fila in filas]
    lista.sort(key=lambda a: (-a["cantidad"],
                              alumnos.clave_de_orden(a["nombre"])))
    return lista[:cantidad]


def resumen_general(conexion, hoy=None, cantidad_dias=7, cantidad_ranking=5):
    """
    Datos para el dashboard.

    - hoy: cantidades del día (presentes, tardanzas, ausentes).
    - totales: todos los registros y el % de asistencia general.
    - dias: los últimos días con registros (hasta hoy), para el gráfico.
    - mas_ausencias / mas_tardanzas: alumnos con más ausencias y más
      tardanzas.
    """
    hoy = hoy or date.today()
    del_dia = resumen_del_dia(conexion, hoy)
    totales = _contar(conexion.execute("SELECT estado FROM asistencias"))
    total_registros = sum(totales.values())
    dias = _dias_recientes(conexion, hoy, cantidad_dias)

    return {
        "alumnos": alumnos.cantidad(conexion),
        "hoy": del_dia["cantidades"],
        "sin_registrar": del_dia["sin_registrar"],
        "totales": totales,
        "total_registros": total_registros,
        "porcentaje_asistencia": porcentaje(
            totales[PRESENTE] + totales[TARDANZA], total_registros),
        "dias": dias,
        "maximo_dia": max((d["total"] for d in dias), default=0),
        "mas_ausencias": _ranking(conexion, AUSENTE, cantidad_ranking),
        "mas_tardanzas": _ranking(conexion, TARDANZA, cantidad_ranking),
    }
