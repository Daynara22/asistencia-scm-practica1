"""
informes.py - Informes de asistencia.

- informe_alumno: un alumno, con filtro opcional por fechas.
- informe_total: resumen general y por curso, con filtros por fechas y
  por curso, y una fila por alumno (para la tabla y la exportación).
- resumen_general: datos del dashboard.

El porcentaje de asistencia cuenta PRESENTE y TARDANZA como asistió
(el alumno vino, aunque tarde). El estado respecto del límite de faltas
siempre se calcula con todos los registros del alumno, sin importar el
filtro de fechas: el límite es para todo el ciclo lectivo.
"""
from datetime import date, datetime

from asistencia.modelos import AUSENTE, PRESENTE, TARDANZA, Curso
from asistencia.servicios import alumnos, cursos, limites
from asistencia.servicios.asistencias import resumen_del_dia
from asistencia.validaciones import ErrorValidacion, validar_fecha

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


def validar_rango(desde_texto, hasta_texto):
    """
    Convierte el filtro de fechas del formulario en (desde, hasta).

    Cualquiera de las dos puede quedar vacía (None = sin límite). Si
    están las dos, 'desde' no puede ser posterior a 'hasta'.
    """
    desde = hasta = None
    if str(desde_texto or "").strip():
        desde = validar_fecha(desde_texto)
    if str(hasta_texto or "").strip():
        hasta = validar_fecha(hasta_texto)
    if desde and hasta and desde > hasta:
        raise ErrorValidacion(
            "La fecha 'desde' no puede ser posterior a la fecha 'hasta'.")
    return desde, hasta


def _condicion_fechas(columna, desde, hasta):
    """
    Fragmento SQL y parámetros para filtrar 'columna' entre dos fechas.

    'columna' es siempre un nombre fijo escrito en este módulo; las
    fechas van como parámetros (?), nunca pegadas en el texto.
    """
    condiciones, parametros = [], []
    if desde:
        condiciones.append(f"{columna} >= ?")
        parametros.append(desde.isoformat())
    if hasta:
        condiciones.append(f"{columna} <= ?")
        parametros.append(hasta.isoformat())
    return " AND ".join(condiciones) or "1 = 1", parametros


def _texto_periodo(desde, hasta):
    """'Del 01/11/2026 al 30/11/2026', 'Desde el ...' o 'Todo el
    período'."""
    if desde and hasta:
        return (f"Del {desde.strftime('%d/%m/%Y')} al "
                f"{hasta.strftime('%d/%m/%Y')}")
    if desde:
        return f"Desde el {desde.strftime('%d/%m/%Y')}"
    if hasta:
        return f"Hasta el {hasta.strftime('%d/%m/%Y')}"
    return "Todo el período"


def _porcentajes(presentes, tardanzas, ausentes):
    """Totales y porcentajes de un grupo de registros."""
    total = presentes + tardanzas + ausentes
    return {
        "presentes": presentes,
        "tardanzas": tardanzas,
        "ausentes": ausentes,
        "total": total,
        "porcentaje_asistencia": porcentaje(presentes + tardanzas, total),
        "porcentaje_presentes": porcentaje(presentes, total),
        "porcentaje_tardanzas": porcentaje(tardanzas, total),
        "porcentaje_ausentes": porcentaje(ausentes, total),
    }


def informe_alumno(conexion, dni, desde=None, hasta=None):
    """
    Informe de un alumno: cantidades, porcentajes y detalle por fecha.

    desde / hasta (objetos date, opcionales) limitan los registros
    contados. La situación respecto del límite usa todos los registros.
    """
    alumno = alumnos.buscar_por_dni(conexion, dni)
    condicion, parametros = _condicion_fechas("fecha", desde, hasta)
    filas = conexion.execute(
        "SELECT fecha, estado, hora, manual FROM asistencias "
        f"WHERE alumno_id = ? AND {condicion} ORDER BY fecha DESC",
        [alumno.id, *parametros]).fetchall()

    detalle = [{
        "fecha": fila["fecha"],
        "fecha_mostrar": _fecha_para_mostrar(fila["fecha"]),
        "estado": fila["estado"],
        "hora": fila["hora"],
        "manual": bool(fila["manual"]),
    } for fila in filas]

    cuenta = _contar(filas)
    curso = None
    if alumno.curso_id:
        curso = cursos.obtener(conexion, alumno.curso_id)
    return {
        "dni": alumno.dni,
        "nombre": alumno.nombre_completo,
        "curso": curso.nombre_completo if curso else None,
        **_porcentajes(cuenta[PRESENTE], cuenta[TARDANZA], cuenta[AUSENTE]),
        "detalle": detalle,
        "periodo": _texto_periodo(desde, hasta),
        "filtrado": bool(desde or hasta),
        # Faltas, límite y estado (normal, cerca o superado).
        "situacion": limites.situacion_alumno(conexion, alumno),
    }


def informe_total(conexion, desde=None, hasta=None, curso_id=None):
    """
    Resumen de asistencia general y por curso.

    Devuelve un diccionario con:
      - general: totales y porcentajes de todos los alumnos filtrados.
      - cursos: lo mismo por cada curso (y "Sin curso" si hay alumnos
        sin curso asignado).
      - alumnos: una fila por alumno con sus cantidades y su estado
        respecto del límite de faltas.
    """
    if curso_id is not None:
        curso_id = cursos.buscar(conexion, curso_id).id
    condicion, parametros = _condicion_fechas("a.fecha", desde, hasta)
    # LEFT JOIN: los alumnos sin registros en el período aparecen con 0.
    filas = conexion.execute(
        "SELECT al.id, al.dni, al.nombre, al.apellido, al.curso_id, "
        "COALESCE(SUM(a.estado = 'PRESENTE'), 0) AS presentes, "
        "COALESCE(SUM(a.estado = 'TARDANZA'), 0) AS tardanzas, "
        "COALESCE(SUM(a.estado = 'AUSENTE'), 0) AS ausentes "
        "FROM alumnos al LEFT JOIN asistencias a "
        f"ON a.alumno_id = al.id AND {condicion} "
        "WHERE ? IS NULL OR al.curso_id = ? GROUP BY al.id",
        [*parametros, curso_id, curso_id]).fetchall()

    nombres = {fila["id"]: Curso.desde_fila(fila).nombre_completo
               for fila in conexion.execute("SELECT * FROM cursos")}
    situaciones = limites.situacion_de_todos(conexion)

    filas_alumnos = [{
        "dni": fila["dni"],
        "nombre": f"{fila['nombre']} {fila['apellido']}",
        "apellido": fila["apellido"],
        "curso_id": fila["curso_id"],
        "curso": nombres.get(fila["curso_id"], "Sin curso"),
        **_porcentajes(fila["presentes"], fila["tardanzas"],
                       fila["ausentes"]),
        "situacion": situaciones[fila["id"]],
    } for fila in filas]
    # Por curso (los sin curso al final) y dentro de cada curso por
    # apellido.
    filas_alumnos.sort(key=lambda a: (
        a["curso_id"] is None, alumnos.clave_de_orden(a["curso"]),
        alumnos.clave_de_orden(a["apellido"]),
        alumnos.clave_de_orden(a["nombre"])))

    return {
        "periodo": _texto_periodo(desde, hasta),
        "curso": nombres.get(curso_id),
        "general": _resumir_grupo("General", filas_alumnos),
        "cursos": _resumir_por_curso(filas_alumnos),
        "alumnos": filas_alumnos,
    }


def _resumir_grupo(nombre, filas_alumnos):
    """Suma las filas de un grupo de alumnos (un curso o todos)."""
    resumen = _porcentajes(
        sum(a["presentes"] for a in filas_alumnos),
        sum(a["tardanzas"] for a in filas_alumnos),
        sum(a["ausentes"] for a in filas_alumnos))
    estados = [a["situacion"]["estado"] for a in filas_alumnos]
    return {"nombre": nombre, "alumnos": len(filas_alumnos), **resumen,
            "cerca": estados.count(limites.CERCA),
            "superados": estados.count(limites.SUPERADO)}


def _resumir_por_curso(filas_alumnos):
    """Un resumen por curso, en el orden en que vienen las filas."""
    grupos = {}
    for fila in filas_alumnos:
        clave = (fila["curso_id"], fila["curso"])
        grupos.setdefault(clave, []).append(fila)
    return [{"id": curso_id, **_resumir_grupo(nombre, filas)}
            for (curso_id, nombre), filas in grupos.items()]


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
