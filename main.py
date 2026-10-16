# main.py - Sistema de Asistencia (v2.0.0 - Breaking Change)
total_asistencias = 0

def registrar_asistencia(datos_alumno: dict):
    global total_asistencias
    dni = datos_alumno.get("dni", "").strip()
    materia = datos_alumno.get("materia", "Programación III")

    if len(dni) >= 7 and dni.isdigit():
        total_asistencias += 1
        print(f"[OK] Asistencia N°{total_asistencias} | DNI: {dni} | Materia: {materia}")
        return True
    print(f"[ERROR] Datos invalidos para DNI: {dni}")
    return False

if __name__ == "__main__":
    print("=== SISTEMA DE ASISTENCIA v2.0.0 ===")
    alumno_ejemplo = {"dni": "40123456", "materia": "Programacion III"}
    registrar_asistencia(alumno_ejemplo)
