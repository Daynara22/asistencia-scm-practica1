"""
Tests del rediseño de la interfaz: menú lateral por rol, botón de modo
claro / oscuro, tarjetas resumen del dashboard y filtros del informe.
"""
import re
from contextlib import closing
from datetime import date

import pytest

from asistencia import bd
from asistencia.interfaz.iconos import TRAZOS, icono
from asistencia.servicios import asistencias, informes, limites
from asistencia.validaciones import ErrorValidacion
from tests.conftest import HOY, a_las, crear_curso, datos_alumno

JUAN = "45123456"

OPCIONES_DOCENTE = ["/", "/asistencia", "/alumnos", "/docentes", "/cursos",
                    "/horarios", "/informes", "/graficos", "/limites"]


def enlaces_del_menu(html):
    """Direcciones de los enlaces del menú lateral."""
    menu = html.split('<nav class="sidebar-nav">')[1].split("</nav>")[0]
    return re.findall(r'href="([^"]+)"', menu)


# ----------------------------------------------------------------------
# Menú lateral
# ----------------------------------------------------------------------

def test_menu_del_administrador(cliente):
    """El administrador ve todas las opciones, incluida Usuarios."""
    enlaces = enlaces_del_menu(cliente.get("/").text)
    assert enlaces == OPCIONES_DOCENTE[:6] + ["/usuarios"] + \
        OPCIONES_DOCENTE[6:]


def test_menu_del_docente(cliente_docente):
    """El docente no ve Usuarios."""
    assert enlaces_del_menu(cliente_docente.get("/").text) == \
        OPCIONES_DOCENTE


def test_menu_del_alumno(cliente_alumno):
    """El alumno solo ve su asistencia y sus gráficos."""
    enlaces = enlaces_del_menu(cliente_alumno.get("/mi-asistencia").text)
    assert enlaces == ["/mi-asistencia", "/graficos"]


@pytest.mark.parametrize("ruta, texto", [
    ("/", "Inicio"), ("/asistencia", "Tomar asistencia"),
    ("/graficos", "Gráficos"), ("/limites", "Configuración"),
    ("/informes", "Informes"), ("/informe", "Informes")])
def test_menu_resalta_la_pantalla_actual(cliente, ruta, texto):
    """La opción actual tiene la clase 'activo' y aria-current."""
    html = cliente.get(ruta).text
    activo = re.search(r'class="sidebar-enlace activo"\s*'
                       r'aria-current="page">.*?<span>(.*?)</span>',
                       html, re.S)
    assert activo and activo.group(1) == texto
    assert html.count('aria-current="page"') == 1


def test_menu_tiene_boton_de_hamburguesa_y_cerrar_sesion(cliente):
    """El menú se abre/cierra con un botón y tiene Cerrar sesión."""
    html = cliente.get("/").text
    assert 'id="boton-menu"' in html and 'aria-controls="sidebar"' in html
    assert 'id="sidebar"' in html
    assert "Cerrar sesión" in html and 'action="/logout"' in html


def test_sin_sesion_no_hay_menu(anonimo):
    """En el login no se muestra el menú lateral."""
    html = anonimo.get("/login").text
    assert 'id="sidebar"' not in html


# ----------------------------------------------------------------------
# Modo claro / oscuro
# ----------------------------------------------------------------------

@pytest.mark.parametrize("ruta", ["/", "/graficos"])
def test_boton_de_tema_con_sesion(cliente, ruta):
    """El botón para cambiar de tema está en la barra superior."""
    html = cliente.get(ruta).text
    assert 'id="boton-tema"' in html
    assert "icono-luna" in html and "icono-sol" in html


@pytest.mark.parametrize("ruta", ["/login", "/registro-docente"])
def test_boton_de_tema_sin_sesion(anonimo, ruta):
    """También se puede cambiar el tema antes de entrar."""
    assert 'id="boton-tema"' in anonimo.get(ruta).text


def test_el_tema_guardado_se_aplica_antes_de_dibujar(anonimo):
    """El tema elegido se lee del navegador al cargar la página."""
    html = anonimo.get("/login").text
    cabecera = html.split("</head>")[0]
    assert 'localStorage.getItem("tema")' in cabecera
    assert "prefers-color-scheme: dark" in cabecera


def test_los_colores_estan_en_variables_para_los_dos_modos(cliente):
    """El CSS define las mismas variables en modo claro y oscuro."""
    css = cliente.get("/static/estilos.css").text
    claro = css.split(":root {")[1].split("}")[0]
    oscuro = css.split('[data-tema="oscuro"] {')[1].split("}")[0]
    variables_claro = set(re.findall(r"(--[\w-]+):", claro))
    variables_oscuro = set(re.findall(r"(--[\w-]+):", oscuro))
    for necesaria in ("--fondo", "--texto", "--superficie", "--c-presente",
                      "--c-tardanza", "--c-ausente", "--c-grilla"):
        assert necesaria in variables_claro and necesaria in variables_oscuro


# ----------------------------------------------------------------------
# Íconos
# ----------------------------------------------------------------------

def test_iconos_decorativos():
    """Los íconos son SVG ocultos para los lectores de pantalla."""
    svg = str(icono("alumnos", "extra"))
    assert svg.startswith('<svg class="icono extra"')
    assert 'aria-hidden="true"' in svg
    assert all(TRAZOS[nombre] for nombre in TRAZOS)


# ----------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------

def test_tarjetas_resumen_del_dashboard(cliente, ruta_memoria):
    """Total de alumnos, % general y alumnos cerca o sobre el límite."""
    cliente.post("/alumnos", data=datos_alumno(JUAN, "Juan", "Pérez"))
    cliente.post("/alumnos", data=datos_alumno("40111222", "Ana", "Díaz"))
    cliente.post("/alumnos", data=datos_alumno("40111333", "Eva", "Luna"))
    with closing(bd.conectar(ruta_memoria)) as conexion:
        limites.cambiar_configuracion(conexion, "2", "0")
        for dia in (2, 3, 4):           # Ana supera el límite (3 de 2)
            asistencias.carga_manual(conexion, "40111222",
                                     f"2026-11-0{dia}", "AUSENTE", "",
                                     hoy=HOY)
        for dia in (2, 3):              # Eva llega al límite (2 de 2)
            asistencias.carga_manual(conexion, "40111333",
                                     f"2026-11-0{dia}", "AUSENTE", "",
                                     hoy=HOY)
        asistencias.registrar(conexion, JUAN,
                              ahora=a_las(8, 0, date(2026, 11, 2)))

    html = cliente.get("/").text
    tarjetas = html.split('id="tarjetas-resumen"')[1].split("</section>")[0]
    valores = re.findall(r'<span class="kpi-valor">(.*?)</span>', tarjetas)
    assert valores == ["3", "16.7%", "1", "1"]
    assert "kpi-aviso" in tarjetas and "kpi-peligro" in tarjetas


def test_tarjetas_resumen_sin_alertas(cliente):
    """Sin alumnos con alerta, las tarjetas quedan en verde."""
    tarjetas = cliente.get("/").text.split('id="tarjetas-resumen"')[1]
    tarjetas = tarjetas.split("</section>")[0]
    assert tarjetas.count("kpi-exito") == 2


# ----------------------------------------------------------------------
# Informe: filtro por alumno y columnas
# ----------------------------------------------------------------------

def test_informe_total_filtrado_por_alumno(con_alumnos):
    """Con DNI, el informe trae solo ese alumno."""
    asistencias.registrar(con_alumnos, JUAN, ahora=a_las(8, 30))
    total = informes.informe_total(con_alumnos, dni=JUAN)
    assert [a["nombre"] for a in total["alumnos"]] == ["Juan Pérez"]
    assert total["alumno"] == "Juan Pérez"
    assert total["general"]["asistidas"] == 1


def test_informe_total_alumno_de_otro_curso(con_alumnos):
    """Alumno y curso que no coinciden: lista vacía, sin errores."""
    otro = crear_curso(con_alumnos, division="B")
    total = informes.informe_total(con_alumnos, curso_id=otro.id, dni=JUAN)
    assert total["alumnos"] == [] and total["alumno"] == "Juan Pérez"


def test_informe_total_alumno_inexistente(con_alumnos):
    """Un DNI que no existe da error claro."""
    with pytest.raises(ErrorValidacion, match="No hay ningún alumno"):
        informes.informe_total(con_alumnos, dni="99999999")


def test_clases_asistidas_suman_presentes_y_tardanzas(con_alumnos):
    """Asistidas = presentes + tardanzas."""
    asistencias.registrar(con_alumnos, JUAN,
                          ahora=a_las(8, 0, date(2026, 11, 2)))
    asistencias.registrar(con_alumnos, JUAN,
                          ahora=a_las(9, 0, date(2026, 11, 3)))
    asistencias.carga_manual(con_alumnos, JUAN, "2026-11-04", "AUSENTE", "",
                             hoy=HOY)
    fila = informes.informe_total(con_alumnos, dni=JUAN)["alumnos"][0]
    assert (fila["asistidas"], fila["tardanzas"], fila["ausentes"]) == \
        (2, 1, 1)
    assert fila["porcentaje_asistencia"] == 66.7


def test_pantalla_de_informes_con_filtro_de_alumno(cliente):
    """La tabla por alumno tiene las columnas pedidas y el filtro."""
    cliente.post("/alumnos", data=datos_alumno(JUAN, "Juan", "Pérez"))
    cliente.post("/alumnos", data=datos_alumno("40111222", "Ana", "Díaz"))
    html = cliente.get(f"/informes?dni={JUAN}").text
    assert 'name="dni"' in html
    for columna in ("Clases asistidas", "Tardanzas", "Inasistencias",
                    "Asistencia", "Estado"):
        assert columna in html
    tabla = html.split('id="tabla-informe-alumnos"')[1]
    assert "Juan Pérez" in tabla and "Ana Díaz" not in tabla
    assert "badge-normal" in tabla and ">\n                Normal</span>" \
        in tabla
    assert f'href="/informes/pdf?dni={JUAN}"' in html
