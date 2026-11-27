"""
limites.py - Límite máximo de faltas y alertas.

- Hay un límite general (por defecto 10 faltas) y cada curso puede tener
  el suyo, que reemplaza al general para sus alumnos.
- Cada AUSENTE es una falta. Cada TARDANZA suma lo que diga
  "valor_tardanza": 0 (no suma, por defecto), 1/4, 1/2 o 1 falta.
- Estados respecto del límite:
    normal    menos del 75 % del límite
    cerca     desde el 75 % del límite hasta el límite inclusive
    superado  más faltas que el límite
"""
from fractions import Fraction

from asistencia.bd import transaccion
from asistencia.modelos import AUSENTE, TARDANZA
from asistencia.servicios import alumnos, cursos
from asistencia.validaciones import ErrorValidacion, validar_entero

LIMITE_POR_DEFECTO = 10
LIMITE_MAXIMO = cursos.LIMITE_MAXIMO
UMBRAL_ALERTA = Fraction(3, 4)      # 75 % del límite

NORMAL = "normal"
CERCA = "cerca"
SUPERADO = "superado"

# Valores permitidos para una tardanza, con el texto para mostrar.
VALORES_TARDANZA = {
    "0": "No suma",
    "0.25": "1/4 de falta",
    "0.5": "1/2 falta",
    "1": "1 falta",
}


# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------

def _leer(conexion, clave, por_defecto):
    """Valor guardado de una opción, o el valor por defecto."""
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


def limite_general(conexion):
    """Cantidad máxima de faltas para quien no tiene límite de curso."""
    return int(_leer(conexion, "limite_faltas", LIMITE_POR_DEFECTO))


def valor_tardanza(conexion):
    """Cuánto suma una tardanza, como texto: '0', '0.25', '0.5' o '1'."""
    return _leer(conexion, "valor_tardanza", "0")


def cambiar_configuracion(conexion, limite_texto, tardanza_texto):
    """Cambia el límite general y el valor de la tardanza."""
    limite = validar_entero(limite_texto, "el límite de faltas", 1,
                            LIMITE_MAXIMO)
    tardanza = str(tardanza_texto or "").strip()
    if tardanza not in VALORES_TARDANZA:
        raise ErrorValidacion(
            "El valor de la tardanza debe ser 0, 1/4, 1/2 o 1 falta.")
    _guardar(conexion, "limite_faltas", str(limite))
    _guardar(conexion, "valor_tardanza", tardanza)
    return limite, tardanza


def limite_para(conexion, curso_id):
    """El límite que corresponde a un alumno de ese curso (o sin
    curso)."""
    if curso_id is not None:
        curso = cursos.obtener(conexion, curso_id)
        if curso and curso.limite_faltas:
            return curso.limite_faltas
    return limite_general(conexion)


# ----------------------------------------------------------------------
# Cálculo de faltas y alertas
# ----------------------------------------------------------------------

def mostrar_numero(valor):
    """Fracción o número para pantalla: 3 -> '3', 2.5 -> '2.5'."""
    valor = float(valor)
    return str(int(valor)) if valor.is_integer() else f"{valor:g}"


def calcular_faltas(ausentes, tardanzas, tardanza_texto):
    """Faltas = ausentes + tardanzas x valor de la tardanza (exacto)."""
    return ausentes + tardanzas * Fraction(tardanza_texto)


def evaluar(faltas, limite):
    """
    Estado de un alumno respecto del límite.

    Devuelve un diccionario con las faltas, el límite, el porcentaje del
    límite ya usado, cuántas faltas le quedan, el estado (normal, cerca o
    superado) y un mensaje para mostrar.
    """
    faltas = Fraction(faltas)
    usado = faltas / limite
    if faltas > limite:
        estado = SUPERADO
        mensaje = (f"Superó el límite de faltas: tiene "
                   f"{mostrar_numero(faltas)} y el máximo es {limite}.")
    elif usado >= UMBRAL_ALERTA:
        estado = CERCA
        mensaje = (f"Está cerca del límite: {mostrar_numero(faltas)} de "
                   f"{limite} faltas ({round(float(usado) * 100)} %).")
    else:
        estado = NORMAL
        mensaje = ""
    return {
        "faltas": float(faltas),
        "faltas_texto": mostrar_numero(faltas),
        "limite": limite,
        "porcentaje_limite": round(float(usado) * 100, 1),
        "restantes": mostrar_numero(max(limite - faltas, 0)),
        "estado": estado,
        "mensaje": mensaje,
    }


def _cuentas_por_alumno(conexion):
    """{alumno_id: (ausentes, tardanzas)} en una sola consulta."""
    filas = conexion.execute(
        "SELECT alumno_id, SUM(estado = ?) AS ausentes, "
        "SUM(estado = ?) AS tardanzas FROM asistencias GROUP BY alumno_id",
        (AUSENTE, TARDANZA))
    return {fila["alumno_id"]: (fila["ausentes"], fila["tardanzas"])
            for fila in filas}


def situacion_alumno(conexion, alumno):
    """Estado de faltas de un alumno (un objeto Alumno)."""
    cuentas = _cuentas_por_alumno(conexion)
    ausentes, tardanzas = cuentas.get(alumno.id, (0, 0))
    faltas = calcular_faltas(ausentes, tardanzas, valor_tardanza(conexion))
    return evaluar(faltas, limite_para(conexion, alumno.curso_id))


def situacion_de_todos(conexion):
    """{alumno_id: situación} de todos los alumnos, para los listados."""
    cuentas = _cuentas_por_alumno(conexion)
    tardanza = valor_tardanza(conexion)
    general = limite_general(conexion)
    limites_curso = {fila["id"]: fila["limite_faltas"] for fila in
                     conexion.execute("SELECT id, limite_faltas FROM cursos")}
    resultado = {}
    for alumno in alumnos.listar(conexion):
        ausentes, tardanzas = cuentas.get(alumno.id, (0, 0))
        limite = limites_curso.get(alumno.curso_id) or general
        resultado[alumno.id] = evaluar(
            calcular_faltas(ausentes, tardanzas, tardanza), limite)
    return resultado


def alumnos_con_alerta(conexion):
    """
    Alumnos cerca del límite o que lo superaron, para el dashboard.

    Primero los que lo superaron; dentro de cada grupo, los que usaron
    más porcentaje del límite.
    """
    situaciones = situacion_de_todos(conexion)
    lista = []
    for alumno in alumnos.listar(conexion):
        situacion = situaciones[alumno.id]
        if situacion["estado"] != NORMAL:
            lista.append({"dni": alumno.dni,
                          "nombre": alumno.nombre_completo, **situacion})
    lista.sort(key=lambda a: (a["estado"] != SUPERADO,
                              -a["porcentaje_limite"]))
    return lista
