"""
graficos.py - Datos y geometría de los gráficos de asistencia.

Los gráficos se dibujan como SVG en las plantillas, sin librerías de
JavaScript. Acá se calcula todo lo numérico (porcentajes, largos de los
arcos, coordenadas de los puntos), así se puede probar con pytest:

- dona():       proporción de presentes, tardanzas y ausentes.
- barras():     % de asistencia de cada alumno de un curso.
- evolucion():  % de asistencia por día (o por semana) en el tiempo.
- geometria_linea(): coordenadas del gráfico de línea.

Los colores no están acá: cada estado tiene una clase CSS (presente,
tardanza, ausente) y el CSS define el color para modo claro y oscuro.
"""
import math
from datetime import datetime, timedelta

from asistencia.modelos import AUSENTE, PRESENTE, TARDANZA
from asistencia.servicios import alumnos, cursos
from asistencia.servicios.informes import condicion_fechas, porcentaje

# Orden fijo de los estados: el color sigue al estado, nunca al ranking.
ESTADOS = (
    ("presente", "Presentes"),
    ("tardanza", "Tardanzas"),
    ("ausente", "Ausentes"),
)
RADIO_DONA = 70
SEPARACION_DONA = 2         # separación (en px) entre los arcos de la dona
MAXIMO_PUNTOS_DIARIOS = 31  # con más días, la evolución se agrupa por semana
MAXIMO_ETIQUETAS_X = 8
DIAS_CORTOS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


# ----------------------------------------------------------------------
# Dona
# ----------------------------------------------------------------------

def dona(presentes, tardanzas, ausentes, radio=RADIO_DONA,
         separacion=SEPARACION_DONA):
    """
    Datos de un gráfico de dona con los tres estados.

    Cada arco se dibuja con un círculo y stroke-dasharray: 'largo' es la
    parte pintada y 'desplazamiento' dónde empieza (en el sentido de las
    agujas del reloj, desde arriba). Entre arcos queda una separación de
    'separacion' px para que no se mezclen los colores.
    """
    valores = dict(zip((clave for clave, _ in ESTADOS),
                       (presentes, tardanzas, ausentes)))
    total = presentes + tardanzas + ausentes
    circunferencia = 2 * math.pi * radio
    visibles = [(clave, etiqueta) for clave, etiqueta in ESTADOS
                if valores[clave] > 0]
    hueco = separacion if len(visibles) > 1 else 0

    segmentos = []
    recorrido = 0.0
    for clave, etiqueta in visibles:
        largo = circunferencia * valores[clave] / total
        pintado = max(largo - hueco, 0.5)
        segmentos.append({
            "clave": clave,
            "etiqueta": etiqueta,
            "valor": valores[clave],
            "porcentaje": porcentaje(valores[clave], total),
            "largo": round(pintado, 2),
            "resto": round(circunferencia - pintado, 2),
            "desplazamiento": round(-recorrido, 2) or 0.0,
        })
        recorrido += largo

    leyenda = [{"clave": clave, "etiqueta": etiqueta,
                "valor": valores[clave],
                "porcentaje": porcentaje(valores[clave], total)}
               for clave, etiqueta in ESTADOS]
    return {
        "total": total,
        "radio": radio,
        "circunferencia": round(circunferencia, 2),
        "segmentos": segmentos,
        "leyenda": leyenda,
        "porcentaje_asistencia": porcentaje(presentes + tardanzas, total),
    }


# ----------------------------------------------------------------------
# Barras por alumno
# ----------------------------------------------------------------------

def barras(filas_alumnos):
    """
    Barras horizontales con el % de asistencia de cada alumno.

    Recibe las filas de informes.informe_total()["alumnos"]. Ordena de
    mayor a menor porcentaje; los alumnos sin registros van al final.
    """
    lista = [{
        "dni": fila["dni"],
        "nombre": fila["nombre"],
        "porcentaje": fila["porcentaje_asistencia"],
        "presentes": fila["presentes"],
        "tardanzas": fila["tardanzas"],
        "ausentes": fila["ausentes"],
        "total": fila["total"],
        "estado": fila["situacion"]["estado"],
        "sin_registros": fila["total"] == 0,
    } for fila in filas_alumnos]
    lista.sort(key=lambda b: (b["sin_registros"], -b["porcentaje"],
                              alumnos.clave_de_orden(b["nombre"])))
    return lista


# ----------------------------------------------------------------------
# Evolución en el tiempo
# ----------------------------------------------------------------------

def evolucion(conexion, desde=None, hasta=None, curso_id=None, dni=None,
              maximo_puntos=MAXIMO_PUNTOS_DIARIOS):
    """
    % de asistencia por fecha, con los mismos filtros que los informes.

    Si hay más de 'maximo_puntos' días con registros, agrupa por semana
    (de lunes a domingo) para que el gráfico se pueda leer. Devuelve
    {"agrupado": "dia" o "semana", "puntos": [...]}.
    """
    if curso_id is not None:
        curso_id = cursos.buscar(conexion, curso_id).id
    alumno_id = alumnos.buscar_por_dni(conexion, dni).id if dni else None
    condicion, parametros = condicion_fechas("a.fecha", desde, hasta)
    filas = conexion.execute(
        "SELECT a.fecha, "
        "SUM(a.estado = ?) AS presentes, SUM(a.estado = ?) AS tardanzas, "
        "SUM(a.estado = ?) AS ausentes "
        "FROM asistencias a JOIN alumnos al ON al.id = a.alumno_id "
        f"WHERE {condicion} AND (? IS NULL OR al.curso_id = ?) "
        "AND (? IS NULL OR al.id = ?) "
        "GROUP BY a.fecha ORDER BY a.fecha",
        [PRESENTE, TARDANZA, AUSENTE, *parametros, curso_id, curso_id,
         alumno_id, alumno_id]).fetchall()

    agrupado = "semana" if len(filas) > maximo_puntos else "dia"
    grupos = {}
    for fila in filas:
        fecha = datetime.strptime(fila["fecha"], "%Y-%m-%d").date()
        if agrupado == "semana":
            fecha -= timedelta(days=fecha.weekday())    # lunes
        cuenta = grupos.setdefault(fecha, [0, 0, 0])
        cuenta[0] += fila["presentes"]
        cuenta[1] += fila["tardanzas"]
        cuenta[2] += fila["ausentes"]

    puntos = []
    for fecha, (pres, tard, aus) in sorted(grupos.items()):
        if agrupado == "semana":
            etiqueta = f"Sem. {fecha.strftime('%d/%m')}"
            detalle = f"Semana del {fecha.strftime('%d/%m/%Y')}"
        else:
            etiqueta = (f"{DIAS_CORTOS[fecha.weekday()]} "
                        f"{fecha.strftime('%d/%m')}")
            detalle = fecha.strftime("%d/%m/%Y")
        total = pres + tard + aus
        puntos.append({
            "fecha": fecha.isoformat(), "etiqueta": etiqueta,
            "detalle": detalle, "presentes": pres, "tardanzas": tard,
            "ausentes": aus, "total": total,
            "porcentaje": porcentaje(pres + tard, total),
        })
    return {"agrupado": agrupado, "puntos": puntos}


def geometria_linea(puntos, ancho=960, alto=300, izquierda=48, derecha=20,
                    arriba=16, abajo=36):
    """
    Coordenadas del gráfico de línea (eje Y de 0 a 100 %).

    Devuelve los puntos con su x / y, el texto para <polyline>, las
    líneas de la grilla (0, 25, 50, 75 y 100 %), qué puntos llevan
    etiqueta en el eje X (como máximo MAXIMO_ETIQUETAS_X) y el ancho de
    la franja que recibe el mouse en cada punto.
    """
    area_ancho = ancho - izquierda - derecha
    area_alto = alto - arriba - abajo
    cantidad = len(puntos)

    def x_de(indice):
        """Posición horizontal del punto número 'indice'."""
        if cantidad == 1:
            return izquierda + area_ancho / 2
        return izquierda + area_ancho * indice / (cantidad - 1)

    def y_de(valor):
        """Posición vertical de un porcentaje (0 abajo, 100 arriba)."""
        return arriba + area_alto * (1 - valor / 100)

    paso = max(1, math.ceil(cantidad / MAXIMO_ETIQUETAS_X))
    resultado = []
    for indice, punto in enumerate(puntos):
        resultado.append({
            **punto,
            "x": round(x_de(indice), 1),
            "y": round(y_de(punto["porcentaje"]), 1),
            # Siempre se rotula el último punto (el más reciente).
            "con_etiqueta": indice % paso == 0 or indice == cantidad - 1,
        })
    franja = area_ancho / (cantidad - 1) if cantidad > 1 else area_ancho
    return {
        "ancho": ancho, "alto": alto,
        "izquierda": izquierda, "derecha": ancho - derecha, "arriba": arriba,
        "base": round(y_de(0), 1),
        "puntos": resultado,
        "linea": " ".join(f"{p['x']},{p['y']}" for p in resultado),
        "grilla": [{"valor": valor, "y": round(y_de(valor), 1)}
                   for valor in (0, 25, 50, 75, 100)],
        "franja": round(franja, 1),
    }
