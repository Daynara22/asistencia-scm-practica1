"""
logica.py - Reglas del sistema de asistencia y validaciones.

Todas las funciones reciben el diccionario "datos" (el contenido del JSON)
y lo modifican. No leen ni guardan archivos: de eso se encarga datos.py.
Si algo está mal, lanzan ErrorValidacion con un mensaje claro para mostrar.
"""
import hashlib
import hmac
import re
import secrets
import string
from datetime import date, datetime, time

PRESENTE = "PRESENTE"
TARDANZA = "TARDANZA"
AUSENTE = "AUSENTE"
ESTADOS = (PRESENTE, TARDANZA, AUSENTE)

# Letras (con tildes y ñ), y palabras separadas por espacio, guion o apóstrofo.
PATRON_NOMBRE = re.compile(r"[^\W\d_]+(?:[ '\-][^\W\d_]+)*")

# Un email simple: algo@dominio.ext (sin espacios).
PATRON_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
CLAVE_MINIMO = 8
CLAVE_MAXIMO = 128


class ErrorValidacion(Exception):
    """Error con un mensaje pensado para mostrarle al usuario."""


# ----------------------------------------------------------------------
# Validaciones
# ----------------------------------------------------------------------

def validar_dni(texto):
    """Devuelve el DNI limpio (solo dígitos) o lanza ErrorValidacion."""
    # Se aceptan puntos y espacios (ej. 45.123.456) y se quitan.
    dni = str(texto or "").strip().replace(".", "").replace(" ", "")
    if not dni:
        raise ErrorValidacion("Ingresá un DNI.")
    if not re.fullmatch(r"[0-9]+", dni):
        raise ErrorValidacion("El DNI solo puede tener números.")
    if len(dni) not in (7, 8):
        raise ErrorValidacion("El DNI debe tener 7 u 8 dígitos.")
    return dni


def validar_nombre(texto, campo):
    """Valida un nombre o apellido y lo devuelve prolijo (ej. 'maría  josé' -> 'María José')."""
    limpio = " ".join(str(texto or "").split())
    if not limpio:
        raise ErrorValidacion(f"El {campo} no puede estar vacío.")
    if len(limpio) > 50:
        raise ErrorValidacion(f"El {campo} no puede tener más de 50 caracteres.")
    if not PATRON_NOMBRE.fullmatch(limpio):
        raise ErrorValidacion(f"El {campo} solo puede tener letras, espacios, guiones o apóstrofos.")
    return limpio.title()


def validar_fecha(texto):
    """Convierte 'AAAA-MM-DD' en un objeto date. Revisa que la fecha exista."""
    texto = str(texto or "").strip()
    if not texto:
        raise ErrorValidacion("Ingresá una fecha.")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", texto):
        raise ErrorValidacion("La fecha debe tener el formato AAAA-MM-DD (por ejemplo 2026-11-06).")
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        raise ErrorValidacion(f"La fecha {texto} no existe.")


def validar_hora(texto):
    """Convierte 'HH:MM' en un objeto time, para comparar horas como horas y no como texto."""
    texto = str(texto or "").strip()
    if not texto:
        raise ErrorValidacion("Ingresá una hora.")
    if not re.fullmatch(r"[0-9]{2}:[0-9]{2}", texto):
        raise ErrorValidacion("La hora debe tener el formato HH:MM (por ejemplo 08:15).")
    try:
        return datetime.strptime(texto, "%H:%M").time()
    except ValueError:
        raise ErrorValidacion(f"La hora {texto} no es válida.")


# ----------------------------------------------------------------------
# Alumnos
# ----------------------------------------------------------------------

def nombre_completo(alumno):
    return f"{alumno['nombre']} {alumno['apellido']}"


def alta_alumno(datos, dni, nombre, apellido):
    """Da de alta un alumno nuevo. Devuelve el alumno creado."""
    dni = validar_dni(dni)
    nombre = validar_nombre(nombre, "nombre")
    apellido = validar_nombre(apellido, "apellido")

    if dni in datos["alumnos"]:
        existente = datos["alumnos"][dni]
        raise ErrorValidacion(f"Ya existe un alumno con el DNI {dni} ({nombre_completo(existente)}).")

    datos["alumnos"][dni] = {"nombre": nombre, "apellido": apellido}
    return datos["alumnos"][dni]


def buscar_alumno(datos, dni):
    """Devuelve (dni_limpio, alumno) o lanza ErrorValidacion si no existe."""
    dni = validar_dni(dni)
    alumno = datos["alumnos"].get(dni)
    if alumno is None:
        raise ErrorValidacion(f"No hay ningún alumno registrado con el DNI {dni}.")
    return dni, alumno


def listar_alumnos(datos):
    """Lista de alumnos ordenada por apellido y nombre. Cada uno incluye su DNI."""
    lista = [{"dni": dni, **alumno} for dni, alumno in datos["alumnos"].items()]
    lista.sort(key=lambda a: (a["apellido"].lower(), a["nombre"].lower()))
    return lista


# ----------------------------------------------------------------------
# Docentes (login)
# ----------------------------------------------------------------------

def validar_email(texto):
    """Devuelve el email limpio y en minúsculas, o lanza ErrorValidacion."""
    email = str(texto or "").strip().lower()
    if not email:
        raise ErrorValidacion("Ingresá un email.")
    if len(email) > 254 or not PATRON_EMAIL.fullmatch(email):
        raise ErrorValidacion("El email no es válido (por ejemplo: nombre@escuela.edu.ar).")
    return email


def validar_clave(clave, repetida):
    """
    Revisa que la contraseña nueva sea segura:
    mínimo 8 caracteres, con al menos una letra, un número y un carácter especial.
    """
    clave = str(clave or "")
    if not clave:
        raise ErrorValidacion("Ingresá una contraseña.")
    if len(clave) < CLAVE_MINIMO:
        raise ErrorValidacion(f"La contraseña debe tener al menos {CLAVE_MINIMO} caracteres.")
    if len(clave) > CLAVE_MAXIMO:
        raise ErrorValidacion(f"La contraseña no puede tener más de {CLAVE_MAXIMO} caracteres.")
    if any(c.isspace() for c in clave):
        raise ErrorValidacion("La contraseña no puede tener espacios.")
    if not any(c.isalpha() for c in clave):
        raise ErrorValidacion("La contraseña debe tener al menos una letra.")
    if not any(c.isdigit() for c in clave):
        raise ErrorValidacion("La contraseña debe tener al menos un número.")
    if all(c.isalnum() for c in clave):
        raise ErrorValidacion("La contraseña debe tener al menos un carácter especial (por ejemplo: ! @ # $ % & * ?).")
    if clave != str(repetida or ""):
        raise ErrorValidacion("Las dos contraseñas no coinciden.")
    return clave


def generar_hash_clave(clave):
    """
    Convierte la contraseña en un hash con scrypt (biblioteca estándar de Python).
    Formato: "scrypt:N:r:p$sal$hash". La sal es distinta para cada contraseña.
    """
    sal = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
    n, r, p = 2 ** 15, 8, 1
    resumen = hashlib.scrypt(clave.encode("utf-8"), salt=sal.encode("utf-8"),
                             n=n, r=r, p=p, maxmem=132 * 1024 * 1024).hex()
    return f"scrypt:{n}:{r}:{p}${sal}${resumen}"


def verificar_clave(hash_guardado, clave):
    """Compara la contraseña con el hash guardado. Acepta los formatos scrypt y pbkdf2."""
    try:
        metodo, sal, esperado = hash_guardado.split("$", 2)
        partes = metodo.split(":")
        if partes[0] == "scrypt":
            n, r, p = (int(x) for x in partes[1:4])
            calculado = hashlib.scrypt(clave.encode("utf-8"), salt=sal.encode("utf-8"),
                                       n=n, r=r, p=p, maxmem=132 * 1024 * 1024).hex()
        elif partes[0] == "pbkdf2":
            algoritmo, iteraciones = partes[1], int(partes[2])
            calculado = hashlib.pbkdf2_hmac(algoritmo, clave.encode("utf-8"),
                                            sal.encode("utf-8"), iteraciones).hex()
        else:
            return False
    except (ValueError, TypeError, IndexError):
        return False
    return hmac.compare_digest(calculado, esperado)


def registrar_docente(datos, email, nombre, apellido, clave, repetida):
    """Crea la cuenta de un docente. La contraseña se guarda como hash. Devuelve (email, docente)."""
    email = validar_email(email)
    nombre = validar_nombre(nombre, "nombre")
    apellido = validar_nombre(apellido, "apellido")
    clave = validar_clave(clave, repetida)

    if email in datos["docentes"]:
        raise ErrorValidacion("Ya existe una cuenta de docente con ese email.")

    datos["docentes"][email] = {
        "nombre": nombre,
        "apellido": apellido,
        "clave": generar_hash_clave(clave),
    }
    return email, datos["docentes"][email]


def autenticar_docente(datos, email, clave):
    """
    Revisa email y contraseña. Devuelve (email, docente) si son correctos.
    El mensaje de error es el mismo en todos los casos, para no revelar
    qué emails tienen cuenta.
    """
    error = ErrorValidacion("El email o la contraseña no son correctos.")
    email = str(email or "").strip().lower()
    clave = str(clave or "")
    if not email or not clave:
        raise ErrorValidacion("Ingresá tu email y tu contraseña.")

    docente = datos["docentes"].get(email)
    if docente is None or not verificar_clave(docente["clave"], clave):
        raise error
    return email, docente


# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------

def obtener_hora_limite(datos):
    return validar_hora(datos["config"]["hora_limite"])


def cambiar_hora_limite(datos, texto):
    hora = validar_hora(texto)
    datos["config"]["hora_limite"] = hora.strftime("%H:%M")
    return datos["config"]["hora_limite"]


# ----------------------------------------------------------------------
# Asistencia
# ----------------------------------------------------------------------

def calcular_estado(hora_llegada, hora_limite):
    """PRESENTE si llegó hasta la hora límite (inclusive), TARDANZA si llegó después."""
    return PRESENTE if hora_llegada <= hora_limite else TARDANZA


def dia_cerrado(datos, fecha):
    return fecha.isoformat() in datos["dias_cerrados"]


def registrar_asistencia(datos, dni, ahora=None):
    """
    Registra la llegada de un alumno con la hora actual.
    El estado (PRESENTE o TARDANZA) se calcula solo según la hora límite.
    """
    ahora = ahora or datetime.now()
    dni, alumno = buscar_alumno(datos, dni)
    hoy = ahora.date()

    if dia_cerrado(datos, hoy):
        raise ErrorValidacion("El día de hoy ya está cerrado: no se pueden registrar más asistencias.")

    registros_de_hoy = datos["asistencias"].get(hoy.isoformat(), {})
    if dni in registros_de_hoy:
        previo = registros_de_hoy[dni]
        detalle = f" a las {previo['hora']}" if previo.get("hora") else ""
        raise ErrorValidacion(
            f"{nombre_completo(alumno)} ya tiene registrada la asistencia de hoy ({previo['estado']}{detalle}).")

    hora_llegada = time(ahora.hour, ahora.minute)
    estado = calcular_estado(hora_llegada, obtener_hora_limite(datos))
    registro = {"estado": estado, "hora": hora_llegada.strftime("%H:%M"), "manual": False}
    datos["asistencias"].setdefault(hoy.isoformat(), {})[dni] = registro

    return {"nombre": nombre_completo(alumno), "dni": dni, **registro}


def carga_manual(datos, dni, fecha_texto, estado, hora_texto=None, hoy=None):
    """
    Carga a mano una TARDANZA o una AUSENCIA (por ejemplo, de un día anterior).
    - TARDANZA: pide la hora de llegada, que debe ser posterior a la hora límite.
    - AUSENTE: no lleva hora.
    """
    hoy = hoy or date.today()
    dni, alumno = buscar_alumno(datos, dni)
    fecha = validar_fecha(fecha_texto)

    if fecha > hoy:
        raise ErrorValidacion("No se puede cargar asistencia de una fecha futura.")

    estado = str(estado or "").strip().upper()
    if estado not in (TARDANZA, AUSENTE):
        raise ErrorValidacion("En la carga manual el estado debe ser TARDANZA o AUSENTE.")

    hora = None
    if estado == TARDANZA:
        if not str(hora_texto or "").strip():
            raise ErrorValidacion("Para cargar una tardanza ingresá la hora de llegada.")
        hora_llegada = validar_hora(hora_texto)
        limite = obtener_hora_limite(datos)
        if hora_llegada <= limite:
            raise ErrorValidacion(
                f"A las {hora_llegada.strftime('%H:%M')} no es tardanza: la hora límite es {limite.strftime('%H:%M')}.")
        hora = hora_llegada.strftime("%H:%M")

    registros_del_dia = datos["asistencias"].get(fecha.isoformat(), {})
    if dni in registros_del_dia:
        previo = registros_del_dia[dni]
        raise ErrorValidacion(
            f"{nombre_completo(alumno)} ya tiene un registro el {fecha.strftime('%d/%m/%Y')} ({previo['estado']}).")

    registro = {"estado": estado, "hora": hora, "manual": True}
    datos["asistencias"].setdefault(fecha.isoformat(), {})[dni] = registro
    return {"nombre": nombre_completo(alumno), "dni": dni, "fecha": fecha.isoformat(), **registro}


def cerrar_dia(datos, hoy=None):
    """Marca AUSENTE a quienes no registraron asistencia hoy y bloquea el día. Devuelve cuántos marcó."""
    hoy = hoy or date.today()
    if dia_cerrado(datos, hoy):
        raise ErrorValidacion("El día de hoy ya estaba cerrado.")

    registros_de_hoy = datos["asistencias"].setdefault(hoy.isoformat(), {})
    marcados = 0
    for dni in datos["alumnos"]:
        if dni not in registros_de_hoy:
            registros_de_hoy[dni] = {"estado": AUSENTE, "hora": None, "manual": False}
            marcados += 1

    datos["dias_cerrados"].append(hoy.isoformat())
    return marcados


def resumen_del_dia(datos, hoy=None):
    """Cantidades del día y la lista de registros, para la pantalla principal."""
    hoy = hoy or date.today()
    registros = datos["asistencias"].get(hoy.isoformat(), {})
    resumen = {PRESENTE: 0, TARDANZA: 0, AUSENTE: 0}
    lista = []
    for dni, registro in registros.items():
        resumen[registro["estado"]] += 1
        alumno = datos["alumnos"].get(dni, {"nombre": "(alumno", "apellido": "eliminado)"})
        lista.append({"dni": dni, "nombre": nombre_completo(alumno), **registro})
    lista.sort(key=lambda r: (r["hora"] is None, r["hora"] or "", r["nombre"]))
    sin_registrar = sum(1 for dni in datos["alumnos"] if dni not in registros)
    return {"cantidades": resumen, "sin_registrar": sin_registrar, "registros": lista}


# ----------------------------------------------------------------------
# Informe
# ----------------------------------------------------------------------

def porcentaje(parte, total):
    return round(parte * 100 / total, 1) if total else 0.0


def informe_alumno(datos, dni):
    """
    Informe completo de un alumno.
    El porcentaje de asistencia cuenta PRESENTE y TARDANZA como asistió
    (el alumno vino, aunque tarde).
    """
    dni, alumno = buscar_alumno(datos, dni)

    detalle = []
    for fecha, registros in datos["asistencias"].items():
        if dni in registros:
            registro = registros[dni]
            detalle.append({
                "fecha": fecha,
                "fecha_mostrar": datetime.strptime(fecha, "%Y-%m-%d").strftime("%d/%m/%Y"),
                "estado": registro["estado"],
                "hora": registro.get("hora"),
                "manual": registro.get("manual", False),
            })
    detalle.sort(key=lambda d: d["fecha"], reverse=True)

    presentes = sum(1 for d in detalle if d["estado"] == PRESENTE)
    tardanzas = sum(1 for d in detalle if d["estado"] == TARDANZA)
    ausentes = sum(1 for d in detalle if d["estado"] == AUSENTE)
    total = len(detalle)

    return {
        "dni": dni,
        "nombre": nombre_completo(alumno),
        "presentes": presentes,
        "tardanzas": tardanzas,
        "ausentes": ausentes,
        "total": total,
        "porcentaje_asistencia": porcentaje(presentes + tardanzas, total),
        "porcentaje_presentes": porcentaje(presentes, total),
        "porcentaje_tardanzas": porcentaje(tardanzas, total),
        "porcentaje_ausentes": porcentaje(ausentes, total),
        "detalle": detalle,
    }


# ----------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------

DIAS_SEMANA = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


def resumen_general(datos, hoy=None, cantidad_dias=7, cantidad_ranking=5):
    """
    Datos para el dashboard:
      - hoy: cantidades del día (presentes, tardanzas, ausentes, sin registrar).
      - totales: todos los registros guardados y el % de asistencia general.
      - dias: los últimos días con registros (hasta hoy), para el gráfico.
      - mas_ausencias / mas_tardanzas: alumnos con más ausencias y más tardanzas.
    """
    hoy = hoy or date.today()
    del_dia = resumen_del_dia(datos, hoy)

    totales = {PRESENTE: 0, TARDANZA: 0, AUSENTE: 0}
    por_alumno = {}
    for registros in datos["asistencias"].values():
        for dni, registro in registros.items():
            totales[registro["estado"]] += 1
            if dni in datos["alumnos"]:
                cuenta = por_alumno.setdefault(dni, {PRESENTE: 0, TARDANZA: 0, AUSENTE: 0})
                cuenta[registro["estado"]] += 1
    total_registros = sum(totales.values())

    fechas = sorted(f for f, registros in datos["asistencias"].items()
                    if registros and f <= hoy.isoformat())[-cantidad_dias:]
    dias = []
    for texto in fechas:
        fecha = datetime.strptime(texto, "%Y-%m-%d").date()
        cuenta = {PRESENTE: 0, TARDANZA: 0, AUSENTE: 0}
        for registro in datos["asistencias"][texto].values():
            cuenta[registro["estado"]] += 1
        dias.append({
            "fecha": texto,
            "etiqueta": f"{DIAS_SEMANA[fecha.weekday()]} {fecha.strftime('%d/%m')}",
            "fecha_mostrar": fecha.strftime("%d/%m/%Y"),
            "presentes": cuenta[PRESENTE],
            "tardanzas": cuenta[TARDANZA],
            "ausentes": cuenta[AUSENTE],
            "total": sum(cuenta.values()),
        })
    maximo = max((d["total"] for d in dias), default=0)

    def ranking(estado):
        lista = [
            {"dni": dni, "nombre": nombre_completo(datos["alumnos"][dni]), "cantidad": cuenta[estado]}
            for dni, cuenta in por_alumno.items() if cuenta[estado] > 0
        ]
        lista.sort(key=lambda a: (-a["cantidad"], a["nombre"].lower()))
        return lista[:cantidad_ranking]

    return {
        "alumnos": len(datos["alumnos"]),
        "hoy": del_dia["cantidades"],
        "sin_registrar": del_dia["sin_registrar"],
        "totales": totales,
        "total_registros": total_registros,
        "porcentaje_asistencia": porcentaje(totales[PRESENTE] + totales[TARDANZA], total_registros),
        "dias": dias,
        "maximo_dia": maximo,
        "mas_ausencias": ranking(AUSENTE),
        "mas_tardanzas": ranking(TARDANZA),
    }
