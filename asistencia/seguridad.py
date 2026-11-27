"""
seguridad.py - Hash y verificación de contraseñas.

Las contraseñas nunca se guardan tal cual: se guarda un hash scrypt
(biblioteca estándar de Python) con una sal distinta para cada una.
"""
import hashlib
import hmac
import secrets
import string

# Parámetros de scrypt: costo, tamaño de bloque y paralelismo.
SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1
MEMORIA_MAXIMA = 132 * 1024 * 1024
LARGO_SAL = 16


def _scrypt(clave, sal, n, r, p):
    """Calcula el hash scrypt de la clave y lo devuelve en hexadecimal."""
    return hashlib.scrypt(clave.encode("utf-8"), salt=sal.encode("utf-8"),
                          n=n, r=r, p=p, maxmem=MEMORIA_MAXIMA).hex()


def generar_hash_clave(clave):
    """
    Convierte la contraseña en un hash.

    Formato: "scrypt:N:r:p$sal$hash".
    """
    alfabeto = string.ascii_letters + string.digits
    sal = "".join(secrets.choice(alfabeto) for _ in range(LARGO_SAL))
    resumen = _scrypt(clave, sal, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"scrypt:{SCRYPT_N}:{SCRYPT_R}:{SCRYPT_P}${sal}${resumen}"


def verificar_clave(hash_guardado, clave):
    """
    Compara la contraseña con el hash guardado.

    Acepta los formatos scrypt y pbkdf2. Si el hash está dañado devuelve
    False en lugar de lanzar un error.
    """
    try:
        metodo, sal, esperado = hash_guardado.split("$", 2)
        partes = metodo.split(":")
        if partes[0] == "scrypt":
            n, r, p = (int(x) for x in partes[1:4])
            calculado = _scrypt(clave, sal, n, r, p)
        elif partes[0] == "pbkdf2":
            algoritmo, iteraciones = partes[1], int(partes[2])
            calculado = hashlib.pbkdf2_hmac(
                algoritmo, clave.encode("utf-8"), sal.encode("utf-8"),
                iteraciones).hex()
        else:
            return False
    except (ValueError, TypeError, IndexError):
        return False
    # compare_digest tarda lo mismo acierte o no (evita ataques de tiempo).
    return hmac.compare_digest(calculado, esperado)
