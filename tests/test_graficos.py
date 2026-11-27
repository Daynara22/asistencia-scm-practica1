"""
Tests de servicios/graficos.py y de la pantalla de gráficos.

Verifica los datos que dibujan los SVG: arcos de la dona, orden de las
barras, puntos de la evolución (por día y por semana) y coordenadas del
gráfico de línea.
"""
import math
from contextlib import closing
from datetime import date

import pytest

from asistencia import bd
from asistencia.servicios import asistencias, graficos, informes
from asistencia.validaciones import ErrorValidacion
from tests.conftest import (HOY, a_las, alta_alumno, crear_curso,
                            datos_alumno)

JUAN, ANA = "45123456", "1234567"


# ----------------------------------------------------------------------
# Dona
# ----------------------------------------------------------------------

def test_dona_porcentajes_y_leyenda():
    """La leyenda siempre trae los tres estados, en orden fijo."""
    dona = graficos.dona(6, 2, 2)
    assert dona["total"] == 10
    assert dona["porcentaje_asistencia"] == 80.0
    assert [(s["clave"], s["porcentaje"]) for s in dona["leyenda"]] == [
        ("presente", 60.0), ("tardanza", 20.0), ("ausente", 20.0)]


def test_dona_arcos_suman_la_circunferencia():
    """Los arcos más las separaciones dan la vuelta completa."""
    dona = graficos.dona(6, 2, 2)
    pintado = sum(s["largo"] for s in dona["segmentos"])
    separaciones = graficos.SEPARACION_DONA * len(dona["segmentos"])
    assert pintado + separaciones == pytest.approx(dona["circunferencia"],
                                                   abs=0.05)
    assert dona["circunferencia"] == pytest.approx(
        2 * math.pi * graficos.RADIO_DONA, abs=0.01)


def test_dona_cada_arco_empieza_donde_termina_el_anterior():
    """El desplazamiento acumula el largo de los arcos anteriores."""
    dona = graficos.dona(6, 2, 2)
    primero, segundo, tercero = dona["segmentos"]
    assert primero["desplazamiento"] == 0.0
    assert segundo["desplazamiento"] == pytest.approx(
        -dona["circunferencia"] * 0.6, abs=0.01)
    assert tercero["desplazamiento"] == pytest.approx(
        -dona["circunferencia"] * 0.8, abs=0.01)


def test_dona_omite_estados_en_cero_y_sin_separacion():
    """Con un solo estado no hay huecos: el anillo queda completo."""
    dona = graficos.dona(5, 0, 0)
    assert [s["clave"] for s in dona["segmentos"]] == ["presente"]
    assert dona["segmentos"][0]["largo"] == pytest.approx(
        dona["circunferencia"], abs=0.01)
    assert len(dona["leyenda"]) == 3


def test_dona_sin_registros():
    """Sin registros no hay arcos ni divisiones por cero."""
    dona = graficos.dona(0, 0, 0)
    assert dona["segmentos"] == [] and dona["total"] == 0
    assert dona["porcentaje_asistencia"] == 0.0


# ----------------------------------------------------------------------
# Barras
# ----------------------------------------------------------------------

def test_barras_ordenadas_y_sin_registros_al_final(con_alumnos):
    """De mayor a menor asistencia; quien no tiene registros, al
    final."""
    alta_alumno(con_alumnos, "40111222", "Zoe", "Álvarez")
    asistencias.registrar(con_alumnos, JUAN, ahora=a_las(8, 0))
    asistencias.carga_manual(con_alumnos, ANA, "2026-11-02", "AUSENTE", "",
                             hoy=HOY)
    asistencias.registrar(con_alumnos, ANA, ahora=a_las(8, 0))
    filas = informes.informe_total(con_alumnos)["alumnos"]

    barras = graficos.barras(filas)

    assert [(b["nombre"], b["porcentaje"], b["sin_registros"])
            for b in barras] == [("Juan Pérez", 100.0, False),
                                 ("Ana Gómez", 50.0, False),
                                 ("Zoe Álvarez", 0.0, True)]
    assert barras[1]["ausentes"] == 1


# ----------------------------------------------------------------------
# Evolución
# ----------------------------------------------------------------------

@pytest.fixture
def con_dias(con_alumnos):
    """Juan y Ana el 2 y el 3 de noviembre: tres asistencias de cuatro."""
    for dia in (2, 3):
        asistencias.registrar(con_alumnos, JUAN,
                              ahora=a_las(8, 0, date(2026, 11, dia)))
    asistencias.registrar(con_alumnos, ANA,
                          ahora=a_las(8, 30, date(2026, 11, 2)))
    asistencias.carga_manual(con_alumnos, ANA, "2026-11-03", "AUSENTE", "",
                             hoy=HOY)
    return con_alumnos


def test_evolucion_por_dia(con_dias):
    """Un punto por fecha con su porcentaje de asistencia."""
    serie = graficos.evolucion(con_dias)
    assert serie["agrupado"] == "dia"
    assert [(p["fecha"], p["porcentaje"]) for p in serie["puntos"]] == [
        ("2026-11-02", 100.0), ("2026-11-03", 50.0)]
    assert serie["puntos"][0]["etiqueta"] == "Lun 02/11"
    assert serie["puntos"][1]["ausentes"] == 1


def test_evolucion_filtrada_por_alumno_y_fechas(con_dias):
    """Los filtros funcionan igual que en los informes."""
    serie = graficos.evolucion(con_dias, dni=ANA)
    assert [p["porcentaje"] for p in serie["puntos"]] == [100.0, 0.0]
    serie = graficos.evolucion(con_dias, desde=date(2026, 11, 3))
    assert [p["fecha"] for p in serie["puntos"]] == ["2026-11-03"]


def test_evolucion_filtrada_por_curso(con_dias):
    """Un curso sin registros no tiene puntos."""
    otro = crear_curso(con_dias, division="B")
    assert graficos.evolucion(con_dias, curso_id=otro.id)["puntos"] == []
    assert len(graficos.evolucion(con_dias, curso_id=1)["puntos"]) == 2


def test_evolucion_agrupa_por_semana(con_dias):
    """Con muchos días, se agrupa por semana (desde el lunes)."""
    asistencias.registrar(con_dias, JUAN,
                          ahora=a_las(8, 0, date(2026, 10, 28)))
    serie = graficos.evolucion(con_dias, maximo_puntos=2)
    assert serie["agrupado"] == "semana"
    assert [(p["fecha"], p["total"]) for p in serie["puntos"]] == [
        ("2026-10-26", 1), ("2026-11-02", 4)]
    assert serie["puntos"][1]["etiqueta"] == "Sem. 02/11"
    assert serie["puntos"][1]["porcentaje"] == 75.0


def test_evolucion_con_filtro_inexistente(con_dias):
    """Un curso o un alumno que no existen dan error claro."""
    with pytest.raises(ErrorValidacion, match="no existe"):
        graficos.evolucion(con_dias, curso_id=99)
    with pytest.raises(ErrorValidacion, match="No hay ningún alumno"):
        graficos.evolucion(con_dias, dni="99999999")


# ----------------------------------------------------------------------
# Geometría del gráfico de línea
# ----------------------------------------------------------------------

def puntos(*porcentajes):
    """Puntos de prueba con solo el porcentaje."""
    return [{"porcentaje": p} for p in porcentajes]


def test_geometria_extremos_y_escala():
    """100 % va arriba, 0 % sobre la base, y los extremos a los
    costados."""
    g = graficos.geometria_linea(puntos(100, 50, 0), ancho=400, alto=200,
                                 izquierda=40, derecha=10, arriba=10,
                                 abajo=30)
    xs = [p["x"] for p in g["puntos"]]
    ys = [p["y"] for p in g["puntos"]]
    assert xs == [40, 215, 390]
    assert ys == [10, 90, 170] and g["base"] == 170
    assert g["linea"] == "40.0,10.0 215.0,90.0 390.0,170.0"
    assert [linea["valor"] for linea in g["grilla"]] == [0, 25, 50, 75, 100]
    assert g["franja"] == 175


def test_geometria_un_solo_punto_queda_centrado():
    """Con un único punto no se divide por cero: va al centro."""
    g = graficos.geometria_linea(puntos(80), ancho=400, izquierda=40,
                                 derecha=10)
    assert g["puntos"][0]["x"] == 215


def test_geometria_rotula_como_maximo_ocho_fechas_y_la_ultima():
    """Con muchas fechas, se rotulan algunas para que no se pisen."""
    g = graficos.geometria_linea(puntos(*range(30)))
    rotuladas = [i for i, p in enumerate(g["puntos"]) if p["con_etiqueta"]]
    assert len(rotuladas) <= graficos.MAXIMO_ETIQUETAS_X + 1
    assert rotuladas[0] == 0 and rotuladas[-1] == 29


# ----------------------------------------------------------------------
# Pantalla de gráficos
# ----------------------------------------------------------------------

@pytest.fixture
def con_registros(cliente, ruta_memoria):
    """Admin con Juan (presente y tarde) y Ana (ausente)."""
    cliente.post("/alumnos", data=datos_alumno(JUAN, "Juan", "Pérez"))
    cliente.post("/alumnos", data=datos_alumno("40111222", "Ana", "Díaz"))
    with closing(bd.conectar(ruta_memoria)) as conexion:
        asistencias.registrar(conexion, JUAN,
                              ahora=a_las(8, 0, date(2026, 11, 2)))
        asistencias.registrar(conexion, JUAN,
                              ahora=a_las(9, 0, date(2026, 11, 3)))
        asistencias.carga_manual(conexion, "40111222", "2026-11-03",
                                 "AUSENTE", "", hoy=HOY)
    return cliente


def test_pantalla_muestra_los_tres_graficos(con_registros):
    """Dona, barras y línea, cada uno con su tabla de datos."""
    r = con_registros.get("/graficos")
    assert r.status_code == 200
    for id_grafico in ("grafico-dona", "grafico-barras", "grafico-linea"):
        assert f'id="{id_grafico}"' in r.text
    assert "arco arco-presente" in r.text and "arco arco-ausente" in r.text
    assert "66.7%" in r.text                 # 2 asistencias de 3
    assert "svg-linea" in r.text
    assert r.text.count("Ver los datos en una tabla") == 2


def test_pantalla_filtrada_por_alumno(con_registros):
    """Con un alumno elegido, la dona y la línea son solo de él."""
    r = con_registros.get(f"/graficos?dni={JUAN}")
    assert "Juan Pérez · Todo el período" in r.text
    assert "100.0%" in r.text


def test_pantalla_con_filtro_invalido(con_registros):
    """Un filtro inválido se explica sin romper la pantalla."""
    r = con_registros.get("/graficos?desde=2026-12-01&hasta=2026-11-01")
    assert r.status_code == 400 and "posterior" in r.text


def test_pantalla_sin_cursos_ni_registros(anonimo):
    """Sin datos, la pantalla abre y lo avisa."""
    anonimo.post("/registro-docente",
                 data={"email": "a@b.com", "nombre": "Ana", "apellido": "Paz",
                       "clave": "Clave123!", "clave_repetida": "Clave123!"})
    r = anonimo.get("/graficos")
    assert r.status_code == 200
    assert "No hay registros para estos filtros" in r.text
    assert 'id="grafico-barras"' in r.text and "Todavía no hay cursos" in \
        r.text


def test_docente_ve_los_graficos(cliente_docente):
    """Los docentes también usan los gráficos."""
    assert cliente_docente.get("/graficos").status_code == 200


def test_alumno_ve_solo_sus_graficos(cliente_alumno, ruta_memoria):
    """El alumno ve su dona y su evolución, sin comparar con otros."""
    with closing(bd.conectar(ruta_memoria)) as conexion:
        asistencias.registrar(conexion, JUAN,
                              ahora=a_las(8, 0, date(2026, 11, 2)))
    # Aunque pida otro DNI, ve los suyos.
    r = cliente_alumno.get("/graficos?dni=1234567&curso=1")
    assert r.status_code == 200
    assert "Juan Pérez" in r.text
    assert 'id="grafico-barras"' not in r.text
    assert 'name="curso"' not in r.text and 'name="dni"' not in r.text
