"""Tests de validaciones.py: DNI, nombres, emails, fechas y horas."""
import pytest

from asistencia import validaciones
from asistencia.validaciones import ErrorValidacion


@pytest.mark.parametrize("dni", ["45123456", "1234567", " 45123456 ",
                                 "45.123.456"])
def test_dni_valido(dni):
    """Se aceptan DNI con espacios o puntos, y se devuelven limpios."""
    assert validaciones.validar_dni(dni) in ("45123456", "1234567")


@pytest.mark.parametrize("dni", ["", "   ", None, "abc12345", "4512345a",
                                 "123456", "123456789", "-1234567",
                                 "12345.6.7.8.9"])
def test_dni_invalido(dni):
    """DNI vacíos, con letras o de largo incorrecto se rechazan."""
    with pytest.raises(ErrorValidacion):
        validaciones.validar_dni(dni)


def test_nombre_se_normaliza():
    """Se quitan espacios de más y se pone mayúscula inicial."""
    assert validaciones.validar_nombre("maría  josé", "nombre") == \
        "María José"
    assert validaciones.validar_nombre("o'brien-núñez", "apellido") == \
        "O'Brien-Núñez"


@pytest.mark.parametrize("nombre", ["", "   ", "Juan2", "P@rez", "x" * 51])
def test_nombre_invalido(nombre):
    """Nombres vacíos, con números o símbolos, o muy largos se
    rechazan."""
    with pytest.raises(ErrorValidacion):
        validaciones.validar_nombre(nombre, "nombre")


def test_email_se_pasa_a_minusculas():
    """El email se guarda sin espacios y en minúsculas."""
    assert validaciones.validar_email("  Ana@Escuela.EDU.ar ") == \
        "ana@escuela.edu.ar"


@pytest.mark.parametrize("email", ["", "maria@", "@escuela.com", "a b@c.com",
                                   "ana@escuela", "ana@@escuela.com"])
def test_email_invalido(email):
    """Emails sin dominio, con espacios o mal formados se rechazan."""
    with pytest.raises(ErrorValidacion):
        validaciones.validar_email(email)


@pytest.mark.parametrize("texto", ["2026-02-30", "2026-13-01", "2026-2-3",
                                   "06/11/2026", "", "hoy"])
def test_fecha_invalida(texto):
    """Fechas inexistentes o con otro formato se rechazan."""
    with pytest.raises(ErrorValidacion):
        validaciones.validar_fecha(texto)


@pytest.mark.parametrize("texto", ["25:00", "08:60", "8:15", "0815", "",
                                   "ocho"])
def test_hora_invalida(texto):
    """Horas inexistentes o con otro formato se rechazan."""
    with pytest.raises(ErrorValidacion):
        validaciones.validar_hora(texto)


@pytest.mark.parametrize("clave, mensaje", [
    ("", "Ingresá una contraseña"),
    ("Ab1!", "al menos 8 caracteres"),
    ("12345678!", "al menos una letra"),
    ("Abcdefgh!", "al menos un número"),
    ("Abcdefg12", "al menos un carácter especial"),
    ("Clave 123!", "espacios"),
])
def test_clave_insegura(clave, mensaje):
    """La contraseña debe cumplir todas las reglas de seguridad."""
    with pytest.raises(ErrorValidacion, match=mensaje):
        validaciones.validar_clave(clave, clave)


def test_claves_distintas():
    """La contraseña y su repetición deben coincidir."""
    with pytest.raises(ErrorValidacion, match="no coinciden"):
        validaciones.validar_clave("Clave123!", "Clave124!")


def test_clave_demasiado_larga():
    """La contraseña tiene un largo máximo."""
    clave = "Clave1!" + "x" * 130
    with pytest.raises(ErrorValidacion, match="más de 128"):
        validaciones.validar_clave(clave, clave)


@pytest.mark.parametrize("texto, mensaje", [
    ("", "vacío"), ("   ", "vacío"), ("x" * 61, "más de 60"),
    ("Mate@mática", "solo puede tener")])
def test_texto_invalido(texto, mensaje):
    """Nombres de materias o cursos vacíos, largos o con símbolos."""
    with pytest.raises(ErrorValidacion, match=mensaje):
        validaciones.validar_texto(texto, "materia")


def test_texto_valido_con_numeros_y_puntos():
    """Se aceptan números, puntos y guiones en materias y cursos."""
    assert validaciones.validar_texto("prog. 2", "materia") == "Prog. 2"
    assert validaciones.validar_texto("Lengua y Lit.", "materia") == \
        "Lengua y Lit."


@pytest.mark.parametrize("texto, mensaje", [
    ("", "Ingresá"), ("3.5", "número"), ("9", "entre")])
def test_entero_invalido(texto, mensaje):
    """Números vacíos, con decimales o fuera de rango se rechazan."""
    with pytest.raises(ErrorValidacion, match=mensaje):
        validaciones.validar_entero(texto, "el año", 1, 7)


@pytest.mark.parametrize("texto", ["", "ABCD", "A-1"])
def test_division_invalida(texto):
    """La división tiene de 1 a 3 letras o números."""
    with pytest.raises(ErrorValidacion):
        validaciones.validar_division(texto)


@pytest.mark.parametrize("texto", [None, "", "abc", "0", "-4"])
def test_id_invalido(texto):
    """Ids que no son números positivos se rechazan."""
    with pytest.raises(ErrorValidacion, match="no existe"):
        validaciones.validar_id(texto, "El curso")
