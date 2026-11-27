"""
rutas_alumnos.py - ABM de alumnos.

Docentes y administradores dan de alta y modifican alumnos; solo los
administradores los dan de baja (se borra también su asistencia).
"""
from fastapi import APIRouter, Depends, Request

from asistencia.interfaz.comun import (flash, obtener_conexion, pagina,
                                       procesar_formulario,
                                       requiere_administrador,
                                       requiere_docente)
from asistencia.servicios import alumnos as servicio_alumnos
from asistencia.servicios import cursos, informes, limites
from asistencia.servicios.alumnos import obtener as obtener_alumno
from asistencia.validaciones import ErrorValidacion

rutas = APIRouter()


def pantalla_alumnos(request, conexion, formulario=None, editando=None,
                     codigo=200, curso_id=None):
    """Arma la pantalla de alumnos (listado y formulario)."""
    lista_cursos = cursos.listar(conexion)
    nombres_cursos = {c["id"]: c["nombre_completo"] for c in lista_cursos}
    porcentajes = informes.porcentajes_por_alumno(conexion)
    situaciones = limites.situacion_de_todos(conexion)
    lista = [{"id": a.id, "dni": a.dni, "nombre": a.nombre,
              "apellido": a.apellido, "email": a.email,
              "curso": nombres_cursos.get(a.curso_id),
              "porcentaje": porcentajes.get(a.id),
              "situacion": situaciones[a.id]}
             for a in servicio_alumnos.listar(conexion, curso_id)]
    return pagina(request, "alumnos.html", codigo, seccion="alumnos",
                  alumnos=lista, cursos=lista_cursos,
                  filtro_curso=str(curso_id or ""),
                  formulario=formulario or {}, editando=editando)


def _datos(formulario):
    """Campos del formulario en el orden que piden los servicios."""
    return (formulario.get("dni"), formulario.get("nombre"),
            formulario.get("apellido"), formulario.get("email"),
            formulario.get("curso_id"))


@rutas.get("/alumnos", name="alumnos")
async def lista_alumnos(request: Request, editar: str = "",
                        curso: str = "",
                        conexion=Depends(obtener_conexion),
                        usuario=Depends(requiere_docente)):
    """
    Listado de alumnos con su % de asistencia.

    Con ?curso=ID muestra solo ese curso; con ?editar=ID, el formulario
    edita ese alumno.
    """
    curso_id = int(curso) if curso.isdigit() else None
    if editar:
        try:
            alumno = servicio_alumnos.buscar(conexion, editar)
        except ErrorValidacion as error:
            flash(request, str(error), "error")
            return pantalla_alumnos(request, conexion, codigo=404)
        formulario = {"dni": alumno.dni, "nombre": alumno.nombre,
                      "apellido": alumno.apellido,
                      "email": alumno.email or "",
                      "curso_id": str(alumno.curso_id or "")}
        return pantalla_alumnos(request, conexion, formulario, alumno,
                                curso_id=curso_id)
    return pantalla_alumnos(request, conexion, curso_id=curso_id)


@rutas.post("/alumnos", name="alta_alumno")
async def alta_alumno(request: Request, conexion=Depends(obtener_conexion),
                      usuario=Depends(requiere_docente)):
    """Da de alta un alumno."""
    return await procesar_formulario(
        request,
        lambda f: servicio_alumnos.alta(conexion, *_datos(f)),
        lambda a: f"Se dio de alta a {a.nombre_completo}.",
        "alumnos",
        lambda f: pantalla_alumnos(request, conexion, f, codigo=400))


@rutas.post("/alumnos/{id}", name="modificar_alumno")
async def modificar_alumno(request: Request, id: str,
                           conexion=Depends(obtener_conexion),
                           usuario=Depends(requiere_docente)):
    """Guarda los cambios de un alumno."""
    editando = obtener_alumno(conexion, int(id)) if id.isdigit() else None
    return await procesar_formulario(
        request,
        lambda f: servicio_alumnos.modificar(conexion, id, *_datos(f)),
        lambda a: f"Se guardaron los cambios de {a.nombre_completo}.",
        "alumnos",
        lambda f: pantalla_alumnos(request, conexion, f, editando, 400))


@rutas.post("/alumnos/{id}/eliminar", name="eliminar_alumno")
async def eliminar_alumno(request: Request, id: str,
                          conexion=Depends(obtener_conexion),
                          usuario=Depends(requiere_administrador)):
    """Da de baja un alumno, con su asistencia y su cuenta."""
    return await procesar_formulario(
        request,
        lambda f: servicio_alumnos.eliminar(conexion, id),
        lambda a: f"Se dio de baja a {a.nombre_completo}.",
        "alumnos",
        lambda f: pantalla_alumnos(request, conexion, codigo=400))
