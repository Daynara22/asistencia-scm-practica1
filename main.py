# main.py - Sistema de Asistencia (v1.0.0)
def registrar_asistencia(dni: str):
    if len(dni) >= 7 and dni.isdigit():
        print(f"[OK] Asistencia registrada exitosamente para DNI: {dni}")
        return True
    print("[ERROR] DNI invalido")
    return False

if __name__ == "__main__":
    print("=== SISTEMA DE ASISTENCIA v1.0.0 ===")
    registrar_asistencia("40123456")