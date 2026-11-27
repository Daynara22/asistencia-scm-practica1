"""
main.py - Sistema de Asistencia (v2.1.0).

Módulo de consola original del proyecto. Registra asistencias en memoria
(sin guardarlas en disco) y arma un reporte estadístico simple.
Se conserva por compatibilidad: lo usa el workflow de verificación de
versiones (verify-release.yml).
"""

total_asistencias = 0
historial_registros = []


def registrar_asistencia(datos_alumno: dict):
    """
    Registra la asistencia de un alumno.

    Recibe un diccionario con "dni" (obligatorio, texto de 7 o más dígitos)
    y "materia" (opcional). Devuelve True si se registró y False si los
    datos no son válidos.
    """
    # Solo se reasigna el contador; la lista se modifica con append.
    global total_asistencias

    dni_raw = datos_alumno.get("dni")
    if not dni_raw or not isinstance(dni_raw, str):
        print("[ERROR] El campo DNI es obligatorio")
        return False

    dni = dni_raw.strip()
    materia = datos_alumno.get("materia", "Programación III")

    if len(dni) >= 7 and dni.isdigit():
        total_asistencias += 1
        registro = {"id": total_asistencias, "dni": dni, "materia": materia}
        historial_registros.append(registro)
        print(f"[OK] Asistencia N°{total_asistencias} | DNI: {dni} "
              f"| Materia: {materia}")
        return True

    print(f"[ERROR] Datos inválidos para DNI: {dni}")
    return False


def obtener_reporte_estadistico():
    """Devuelve el total de asistencias y el detalle de cada registro."""
    return {
        "total_asistencias": total_asistencias,
        "detalle": historial_registros,
    }


if __name__ == "__main__":
    print("=== SISTEMA DE ASISTENCIA v2.1.0 ===")
    registrar_asistencia({"dni": "40123456", "materia": "Programación III"})
    print("Reporte:", obtener_reporte_estadistico())
