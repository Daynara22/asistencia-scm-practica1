"""rutas_alumnos.py - Alta y listado de alumnos, e informe por alumno."""
from dataclasses import asdict

from fastapi import APIRouter, Depends, Request

from asistencia.interfaz.comun import (flash, obtener_conexion, pagina,
                                       redirigir, requiere_alumno,
                                       requiere_docente)
from asistencia.servicios import alumnos as servicio_alumnos
from asistencia.servicios import informes
from asistencia.servicios.alumnos import obtener as obtener_alumno
from asistencia.validaciones import ErrorValidacion

rutas = APIRouter()


@rutas.api_route("/alumnos", methods=["GET", "POST"], name="alumnos")
async def alumnos(request: Request, conexion=Depends(obtener_conexion),
                  usuario=Depends(requiere_docente)):
    """Formulario de alta y listado de alumnos con su % de asistencia."""
    formulario = {}
    if request.method == "POST":
        formulario = await request.form()
        try:
            alumno = servicio_alumnos.alta(
                conexion, formulario.get("dni"), formulario.get("nombre"),
                formulario.get("apellido"))
        except ErrorValidacion as error:
            flash(request, str(error), "error")
        else:
            flash(request, f"Se dio de alta a {alumno.nombre_completo}.",
                  "exito")
            return redirigir(request, "alumnos")

    porcentajes = informes.porcentajes_por_alumno(conexion)
    lista = [{**asdict(a), "porcentaje": porcentajes.get(a.id)}
             for a in servicio_alumnos.listar(conexion)]
    codigo = 400 if request.method == "POST" else 200
    return pagina(request, "alumnos.html", codigo, seccion="alumnos",
                  alumnos=lista, formulario=formulario)


@rutas.get("/informe", name="informe")
async def informe(request: Request, dni: str = "",
                  conexion=Depends(obtener_conexion),
                  usuario=Depends(requiere_docente)):
    """Informe de asistencia de un alumno, buscado por DNI."""
    dni = dni.strip()
    resultado = None
    codigo = 200
    if dni:
        try:
            resultado = informes.informe_alumno(conexion, dni)
        except ErrorValidacion as error:
            flash(request, str(error), "error")
            codigo = 400
    return pagina(request, "informe.html", codigo, seccion="informe",
                  dni=dni, informe=resultado)


@rutas.get("/mi-asistencia", name="mi_asistencia")
async def mi_asistencia(request: Request,
                        conexion=Depends(obtener_conexion),
                        usuario=Depends(requiere_alumno)):
    """Informe propio del alumno que inició sesión (solo el suyo)."""
    alumno = obtener_alumno(conexion, usuario.alumno_id)
    resultado = informes.informe_alumno(conexion, alumno.dni)
    return pagina(request, "informe.html", seccion="mi_asistencia",
                  dni=alumno.dni, informe=resultado, propio=True)
