"""
rutas_informes.py - Panel de informes de asistencia y exportación.

- /informe          informe de un alumno (docentes y administradores)
- /informes         informe total, general y por curso
- /mi-asistencia    informe propio del alumno que inició sesión
Cada uno acepta filtro por fechas (?desde=AAAA-MM-DD&hasta=AAAA-MM-DD)
y se puede descargar en CSV o PDF agregando /csv o /pdf a la dirección.
"""
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from asistencia import exportar
from asistencia.interfaz.comun import (flash, obtener_conexion, pagina,
                                       requiere_alumno, requiere_docente)
from asistencia.servicios import alumnos, cursos, informes
from asistencia.validaciones import ErrorValidacion

rutas = APIRouter()

TIPO_CSV = "text/csv; charset=utf-8"
TIPO_PDF = "application/pdf"


def descargar(contenido, nombre_archivo, tipo):
    """Respuesta que el navegador guarda como archivo."""
    return Response(
        contenido, media_type=tipo,
        headers={"Content-Disposition":
                 f'attachment; filename="{nombre_archivo}"'})


def _sufijo_fecha():
    """Fecha de hoy para el nombre del archivo: 2026-11-26."""
    return date.today().isoformat()


# ----------------------------------------------------------------------
# Informe por alumno
# ----------------------------------------------------------------------

def _informe_alumno(conexion, dni, desde, hasta):
    """Valida el filtro y arma el informe del alumno."""
    desde, hasta = informes.validar_rango(desde, hasta)
    return informes.informe_alumno(conexion, dni, desde, hasta)


def pantalla_informe(request, conexion, dni, desde, hasta, propio=False):
    """Arma la pantalla del informe de un alumno (o la propia del
    alumno)."""
    resultado, codigo = None, 200
    if dni:
        try:
            resultado = _informe_alumno(conexion, dni, desde, hasta)
        except ErrorValidacion as error:
            flash(request, str(error), "error")
            codigo = 400
    seccion = "mi_asistencia" if propio else "informe"
    return pagina(request, "informe.html", codigo, seccion=seccion,
                  dni=dni, desde=desde, hasta=hasta, informe=resultado,
                  propio=propio)


@rutas.get("/informe", name="informe")
async def informe(request: Request, dni: str = "", desde: str = "",
                  hasta: str = "", conexion=Depends(obtener_conexion),
                  usuario=Depends(requiere_docente)):
    """Informe de asistencia de un alumno, buscado por DNI."""
    return pantalla_informe(request, conexion, dni.strip(), desde, hasta)


@rutas.get("/informe/{formato}", name="exportar_informe")
async def exportar_informe(request: Request, formato: str, dni: str = "",
                           desde: str = "", hasta: str = "",
                           conexion=Depends(obtener_conexion),
                           usuario=Depends(requiere_docente)):
    """Descarga el informe de un alumno en CSV o PDF."""
    return _exportar_alumno(request, conexion, formato, dni.strip(), desde,
                            hasta)


def _exportar_alumno(request, conexion, formato, dni, desde, hasta,
                     propio=False):
    """Arma el archivo del informe de un alumno, o muestra el error."""
    if formato not in ("csv", "pdf"):
        return pagina(request, "error.html", 404, codigo=404,
                      mensaje="La página que buscás no existe.")
    try:
        resultado = _informe_alumno(conexion, dni, desde, hasta)
    except ErrorValidacion:
        # La pantalla vuelve a armar el informe y muestra el mensaje.
        return pantalla_informe(request, conexion, dni, desde, hasta,
                                propio)
    nombre = f"asistencia-{resultado['dni']}-{_sufijo_fecha()}.{formato}"
    if formato == "csv":
        return descargar(exportar.csv_alumno(resultado), nombre, TIPO_CSV)
    return descargar(exportar.pdf_alumno(resultado), nombre, TIPO_PDF)


# ----------------------------------------------------------------------
# Mi asistencia (alumno)
# ----------------------------------------------------------------------

def _dni_propio(conexion, usuario):
    """DNI del alumno vinculado a la cuenta que inició sesión."""
    return alumnos.obtener(conexion, usuario.alumno_id).dni


@rutas.get("/mi-asistencia", name="mi_asistencia")
async def mi_asistencia(request: Request, desde: str = "", hasta: str = "",
                        conexion=Depends(obtener_conexion),
                        usuario=Depends(requiere_alumno)):
    """Informe propio del alumno que inició sesión (solo el suyo)."""
    return pantalla_informe(request, conexion,
                            _dni_propio(conexion, usuario), desde, hasta,
                            propio=True)


@rutas.get("/mi-asistencia/{formato}", name="exportar_mi_asistencia")
async def exportar_mi_asistencia(request: Request, formato: str,
                                 desde: str = "", hasta: str = "",
                                 conexion=Depends(obtener_conexion),
                                 usuario=Depends(requiere_alumno)):
    """El alumno descarga su propio informe en CSV o PDF."""
    return _exportar_alumno(request, conexion, formato,
                            _dni_propio(conexion, usuario), desde, hasta,
                            propio=True)


# ----------------------------------------------------------------------
# Informe total
# ----------------------------------------------------------------------

def _informe_total(conexion, desde, hasta, curso):
    """Valida los filtros y arma el informe total."""
    desde, hasta = informes.validar_rango(desde, hasta)
    curso_id = curso if str(curso or "").strip() else None
    return informes.informe_total(conexion, desde, hasta, curso_id)


def pantalla_informe_total(request, conexion, desde, hasta, curso):
    """Arma la pantalla del informe total."""
    try:
        resultado, codigo = _informe_total(conexion, desde, hasta,
                                           curso), 200
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        resultado, codigo = None, 400
    return pagina(request, "informes.html", codigo, seccion="informe",
                  informe=resultado, cursos=cursos.listar(conexion),
                  filtro={"desde": desde, "hasta": hasta, "curso": curso})


@rutas.get("/informes", name="informe_total")
async def informe_total(request: Request, desde: str = "", hasta: str = "",
                        curso: str = "", conexion=Depends(obtener_conexion),
                        usuario=Depends(requiere_docente)):
    """Resumen general y por curso, con filtros."""
    return pantalla_informe_total(request, conexion, desde, hasta, curso)


@rutas.get("/informes/{formato}", name="exportar_informe_total")
async def exportar_informe_total(request: Request, formato: str,
                                 desde: str = "", hasta: str = "",
                                 curso: str = "",
                                 conexion=Depends(obtener_conexion),
                                 usuario=Depends(requiere_docente)):
    """Descarga el informe total en CSV o PDF."""
    if formato not in ("csv", "pdf"):
        return pagina(request, "error.html", 404, codigo=404,
                      mensaje="La página que buscás no existe.")
    try:
        resultado = _informe_total(conexion, desde, hasta, curso)
    except ErrorValidacion:
        # La pantalla vuelve a armar el informe y muestra el mensaje.
        return pantalla_informe_total(request, conexion, desde, hasta, curso)
    nombre = f"asistencia-total-{_sufijo_fecha()}.{formato}"
    if formato == "csv":
        return descargar(exportar.csv_total(resultado), nombre, TIPO_CSV)
    return descargar(exportar.pdf_total(resultado), nombre, TIPO_PDF)
