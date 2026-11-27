"""
Tests de exportar.py (CSV y PDF) y de las descargas desde la web.

Los PDF se revisan por su encabezado y su tamaño; los CSV, leyendo el
contenido con el módulo csv, como lo haría una planilla de cálculo.
"""
import csv
import io
import re
from contextlib import closing
from datetime import date

import pytest

from asistencia import bd, exportar
from asistencia.servicios import asistencias, informes, limites
from tests.conftest import HOY, a_las, alta_alumno, datos_alumno

JUAN = "45123456"


def leer_csv(texto):
    """Filas del CSV, como las vería Excel."""
    assert texto.startswith("﻿")            # marca UTF-8 para Excel
    return list(csv.reader(io.StringIO(texto[1:]), delimiter=";"))


@pytest.fixture
def con_registros(con_alumnos):
    """Juan: presente, tardanza y ausente; límite 4 (queda cerca)."""
    asistencias.registrar(con_alumnos, JUAN,
                          ahora=a_las(8, 0, date(2026, 11, 2)))
    asistencias.registrar(con_alumnos, JUAN,
                          ahora=a_las(8, 40, date(2026, 11, 3)))
    for dia in (4, 5, 6):
        asistencias.carga_manual(con_alumnos, JUAN, f"2026-11-0{dia}",
                                 "AUSENTE", "", hoy=HOY)
    limites.cambiar_configuracion(con_alumnos, "4", "0")
    return con_alumnos


# ----------------------------------------------------------------------
# CSV
# ----------------------------------------------------------------------

def test_csv_alumno(con_registros):
    """El CSV del alumno trae resumen, estado y detalle por fecha."""
    filas = leer_csv(exportar.csv_alumno(
        informes.informe_alumno(con_registros, JUAN)))
    assert ["Alumno", "Juan Pérez"] in filas
    assert ["Curso", "Programación 3° A"] in filas
    indice = filas.index(["Presentes", "Tardanzas", "Ausentes",
                          "Días registrados", "% asistencia", "Faltas",
                          "Límite", "Estado"])
    assert filas[indice + 1] == ["1", "1", "3", "5", "40,0", "3", "4",
                                 "Cerca del límite"]
    assert ["06/11/2026", "AUSENTE", "", "Manual"] in filas
    assert ["03/11/2026", "TARDANZA", "08:40", "Automática"] in filas


def test_csv_total(con_registros):
    """El CSV total trae una fila por curso, la general y una por
    alumno."""
    filas = leer_csv(exportar.csv_total(informes.informe_total(
        con_registros)))
    assert ["General", "2", "1", "1", "3", "40,0", "1", "0"] in filas
    juan = [f for f in filas if f and f[0] == JUAN][0]
    assert juan[1:3] == ["Juan Pérez", "Programación 3° A"]
    assert juan[-1] == "Cerca del límite"


def test_csv_con_decimales_y_punto_y_coma(con_registros):
    """Decimales con coma y punto y coma como separador (Excel en
    español)."""
    limites.cambiar_configuracion(con_registros, "4", "0.5")
    texto = exportar.csv_alumno(informes.informe_alumno(con_registros,
                                                        JUAN))
    assert ";3,5;" in texto          # 3 ausencias + 1/2 de la tardanza


# ----------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------

def test_pdf_alumno(con_registros):
    """El PDF del alumno es un archivo PDF válido."""
    contenido = exportar.pdf_alumno(
        informes.informe_alumno(con_registros, JUAN))
    assert contenido.startswith(b"%PDF-")
    assert contenido.rstrip().endswith(b"%%EOF")
    assert len(contenido) > 1000


def test_pdf_total(con_registros):
    """El PDF total es un archivo PDF válido."""
    contenido = exportar.pdf_total(informes.informe_total(con_registros))
    assert contenido.startswith(b"%PDF-") and len(contenido) > 1000


def test_pdf_sin_registros(con_alumnos):
    """Un alumno sin registros también genera su PDF."""
    contenido = exportar.pdf_alumno(
        informes.informe_alumno(con_alumnos, "1234567"))
    assert contenido.startswith(b"%PDF-")


def test_pdf_con_muchos_alumnos_ocupa_varias_paginas(con_alumnos):
    """Con muchos alumnos el PDF agrega páginas solo."""
    for numero in range(80):
        alta_alumno(con_alumnos, str(30000000 + numero), "Alumno",
                    "Prueba")
    contenido = exportar.pdf_total(informes.informe_total(con_alumnos))
    # El árbol de páginas del PDF dice cuántas hay: "/Count N".
    paginas = int(re.search(rb"/Count (\d+)", contenido).group(1))
    assert paginas >= 2


def test_texto_pdf_reemplaza_caracteres_raros():
    """Los caracteres que Helvetica no tiene se reemplazan, sin
    fallar."""
    assert exportar._texto_pdf("Ver → informe — ok") == \
        "Ver -> informe - ok"
    assert exportar._texto_pdf("Pérez 3° Ñandú") == "Pérez 3° Ñandú"
    assert exportar._texto_pdf("emoji 😀") == "emoji ?"


# ----------------------------------------------------------------------
# Descargas desde la web
# ----------------------------------------------------------------------

@pytest.fixture
def cliente_con_datos(cliente, ruta_memoria):
    """Cliente admin con Juan y algunos registros."""
    cliente.post("/alumnos", data=datos_alumno(JUAN, "Juan", "Pérez"))
    with closing(bd.conectar(ruta_memoria)) as conexion:
        asistencias.registrar(conexion, JUAN,
                              ahora=a_las(8, 0, date(2026, 11, 2)))
    return cliente


@pytest.mark.parametrize("formato, tipo, inicio", [
    ("csv", "text/csv", b"\xef\xbb\xbf"),
    ("pdf", "application/pdf", b"%PDF-"),
])
def test_descargar_informe_de_alumno(cliente_con_datos, formato, tipo,
                                     inicio):
    """El informe del alumno se descarga como archivo."""
    r = cliente_con_datos.get(f"/informe/{formato}?dni={JUAN}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(tipo)
    assert "attachment" in r.headers["content-disposition"]
    assert f"asistencia-{JUAN}-" in r.headers["content-disposition"]
    assert r.content.startswith(inicio)


@pytest.mark.parametrize("formato", ["csv", "pdf"])
def test_descargar_informe_total(cliente_con_datos, formato):
    """El informe total se descarga con los filtros aplicados."""
    r = cliente_con_datos.get(
        f"/informes/{formato}?desde=2026-11-01&hasta=2026-11-30&curso=1")
    assert r.status_code == 200
    assert "asistencia-total-" in r.headers["content-disposition"]


def test_descarga_csv_respeta_el_filtro(cliente_con_datos):
    """Fuera del período, el CSV muestra cero registros."""
    r = cliente_con_datos.get(
        f"/informe/csv?dni={JUAN}&desde=2026-12-01")
    filas = leer_csv(r.content.decode("utf-8"))
    assert ["Período", "Desde el 01/12/2026"] in filas
    assert filas[filas.index(["Presentes", "Tardanzas", "Ausentes",
                              "Días registrados", "% asistencia",
                              "Faltas", "Límite", "Estado"]) + 1][:4] == \
        ["0", "0", "0", "0"]


def test_descarga_con_error_muestra_la_pantalla(cliente_con_datos):
    """Con un filtro inválido no se descarga nada: se explica el
    error."""
    r = cliente_con_datos.get(
        f"/informe/pdf?dni={JUAN}&desde=2026-12-01&hasta=2026-11-01")
    assert r.status_code == 400 and "posterior" in r.text
    assert r.text.count("posterior a la fecha") == 1     # sin duplicar


def test_formato_desconocido(cliente_con_datos):
    """Solo existen CSV y PDF."""
    assert cliente_con_datos.get(
        f"/informe/xls?dni={JUAN}").status_code == 404
    assert cliente_con_datos.get("/informes/doc").status_code == 404


def test_alumno_descarga_solo_su_informe(cliente_alumno):
    """El alumno descarga su propio informe; no puede pedir el de
    otro."""
    r = cliente_alumno.get("/mi-asistencia/pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF-")
    assert JUAN in r.headers["content-disposition"]
    assert cliente_alumno.get("/informe/pdf?dni=1234567").status_code == \
        403
    assert cliente_alumno.get("/informes/csv").status_code == 403
