"""Tests de migracion.py y del script migrar_json.py."""
import json
from contextlib import closing

import pytest

import migrar_json
from asistencia import bd
from asistencia.migracion import ErrorMigracion, importar, leer_json
from asistencia.servicios import (alumnos, configuracion, informes,
                                  usuarios)
from asistencia.seguridad import generar_hash_clave

DATOS_JSON = {
    "config": {"hora_limite": "07:45"},
    "alumnos": {
        "45123456": {"nombre": "Juan", "apellido": "Pérez"},
        "1234567": {"nombre": "Ana", "apellido": "Gómez"},
    },
    "asistencias": {
        "2026-11-05": {
            "45123456": {"estado": "PRESENTE", "hora": "07:40",
                         "manual": False},
            "1234567": {"estado": "AUSENTE", "hora": None, "manual": False},
        },
        "2026-11-06": {
            "45123456": {"estado": "TARDANZA", "hora": "08:10",
                         "manual": True},
            "99999999": {"estado": "PRESENTE", "hora": "07:00",
                         "manual": False},
        },
    },
    "dias_cerrados": ["2026-11-05"],
    "docentes": {
        "maria@escuela.edu.ar": {"nombre": "María", "apellido": "González",
                                 "clave": generar_hash_clave("Clave123!")},
    },
}


@pytest.fixture
def archivo_json(tmp_path):
    """Archivo JSON de prueba con el formato de la versión anterior."""
    ruta = tmp_path / "asistencia.json"
    ruta.write_text(json.dumps(DATOS_JSON, ensure_ascii=False),
                    encoding="utf-8")
    return ruta


def test_importa_todo(conexion, archivo_json):
    """Pasan alumnos, asistencias, días cerrados, docentes y la hora
    límite."""
    resultado = importar(conexion, leer_json(str(archivo_json)))
    # El registro del DNI 99999999 se saltea: ese alumno no existe.
    assert resultado == {"alumnos": 2, "asistencias": 3,
                         "dias_cerrados": 1, "docentes": 1}
    assert configuracion.texto_hora_limite(conexion) == "07:45"
    informe = informes.informe_alumno(conexion, "45123456")
    assert (informe["presentes"], informe["tardanzas"]) == (1, 1)
    assert informe["detalle"][0]["manual"] is True


def test_docente_migrado_puede_entrar(conexion, archivo_json):
    """El hash de la clave se copia tal cual: la misma clave sigue
    sirviendo."""
    importar(conexion, leer_json(str(archivo_json)))
    usuario = usuarios.autenticar(conexion, "maria@escuela.edu.ar",
                                  "Clave123!")
    assert usuario.nombre_completo == "María González"


def test_importar_dos_veces_no_duplica(conexion, archivo_json):
    """Repetir la migración no agrega nada nuevo."""
    datos = leer_json(str(archivo_json))
    importar(conexion, datos)
    segunda = importar(conexion, datos)
    assert segunda == {"alumnos": 0, "asistencias": 0, "dias_cerrados": 0,
                       "docentes": 0}
    assert alumnos.cantidad(conexion) == 2


@pytest.mark.parametrize("contenido", [
    "{esto no es json", "[]", '{"alumnos": 5}', "",
    '{"config": {"hora_limite": "25:99"}}',
])
def test_json_danado_da_error_claro(tmp_path, contenido):
    """Un JSON roto o con otra forma se informa sin romper nada."""
    ruta = tmp_path / "asistencia.json"
    ruta.write_text(contenido, encoding="utf-8")
    with pytest.raises(ErrorMigracion):
        leer_json(str(ruta))


def test_script_migrar_json(tmp_path, archivo_json, monkeypatch, capsys):
    """El script usa la base indicada en ASISTENCIA_BD y no toca el
    JSON."""
    ruta_bd = tmp_path / "migrada.db"
    monkeypatch.setenv("ASISTENCIA_BD", str(ruta_bd))
    original = archivo_json.read_text(encoding="utf-8")

    assert migrar_json.main([str(archivo_json)]) == 0
    assert "alumnos: 2" in capsys.readouterr().out
    assert archivo_json.read_text(encoding="utf-8") == original
    with closing(bd.conectar(str(ruta_bd))) as conexion:
        assert alumnos.cantidad(conexion) == 2


def test_script_sin_archivo(tmp_path, capsys):
    """Si el JSON no existe, el script avisa y termina con error."""
    assert migrar_json.main([str(tmp_path / "no-existe.json")]) == 1
    assert "No se encontró" in capsys.readouterr().out


@pytest.mark.parametrize("cambio", [
    {"alumnos": {"45123456": {"nombre": "Juan"}}},
    {"alumnos": {"45123456": "Juan Pérez"}},
    {"asistencias": {"2026-11-05": {"45123456": {"estado": "FERIADO"}}}},
    {"docentes": {"a@b.com": {"nombre": "Ana", "apellido": "Díaz"}}},
    {"alumnos": ["no", "es", "un", "objeto"]},
])
def test_json_con_datos_incompletos(tmp_path, cambio):
    """Cada parte del JSON se revisa antes de importar."""
    ruta = tmp_path / "asistencia.json"
    ruta.write_text(json.dumps({**DATOS_JSON, **cambio}), encoding="utf-8")
    with pytest.raises(ErrorMigracion):
        leer_json(str(ruta))


def test_script_con_json_danado(tmp_path, monkeypatch, capsys):
    """El script avisa si el JSON está dañado y no crea nada."""
    ruta = tmp_path / "asistencia.json"
    ruta.write_text("{roto", encoding="utf-8")
    monkeypatch.setenv("ASISTENCIA_BD", str(tmp_path / "nueva.db"))
    assert migrar_json.main([str(ruta)]) == 1
    assert "No se pudo migrar" in capsys.readouterr().out
    assert not (tmp_path / "nueva.db").exists()
