"""
rutas_docentes.py - Pantalla de ABM de docentes.

Docentes y administradores ven el listado; solo los administradores
pueden dar de alta, modificar o dar de baja.
"""
from fastapi import APIRouter, Depends, Request

from asistencia.interfaz.comun import (flash, obtener_conexion, pagina,
                                       procesar_formulario,
                                       requiere_administrador,
                                       requiere_docente)
from asistencia.servicios import docentes, materias
from asistencia.validaciones import ErrorValidacion

rutas = APIRouter()


def pantalla_docentes(request, conexion, formulario=None, editando=None,
                      codigo=200):
    """Arma la pantalla de docentes (listado y formulario)."""
    return pagina(request, "docentes.html", codigo, seccion="docentes",
                  docentes=docentes.listar(conexion),
                  materias=materias.listar(conexion),
                  formulario=formulario or {}, editando=editando)


def _datos(formulario):
    """Campos del formulario en el orden que piden los servicios."""
    return (formulario.get("dni"), formulario.get("nombre"),
            formulario.get("apellido"), formulario.get("email"),
            formulario.get("materias"))


@rutas.get("/docentes", name="docentes")
async def lista_docentes(request: Request, editar: str = "",
                         conexion=Depends(obtener_conexion),
                         usuario=Depends(requiere_docente)):
    """Listado de docentes. Con ?editar=ID, el formulario edita ese
    docente."""
    if editar and usuario.es_administrador:
        try:
            docente = docentes.buscar(conexion, editar)
        except ErrorValidacion as error:
            flash(request, str(error), "error")
            return pantalla_docentes(request, conexion, codigo=404)
        formulario = {"dni": docente.dni, "nombre": docente.nombre,
                      "apellido": docente.apellido, "email": docente.email,
                      "materias": ", ".join(docente.materias)}
        return pantalla_docentes(request, conexion, formulario, docente)
    return pantalla_docentes(request, conexion)


@rutas.post("/docentes", name="alta_docente")
async def alta_docente(request: Request, conexion=Depends(obtener_conexion),
                       usuario=Depends(requiere_administrador)):
    """Da de alta un docente."""
    return await procesar_formulario(
        request,
        lambda f: docentes.alta(conexion, *_datos(f)),
        lambda d: f"Se dio de alta a {d.nombre_completo}.",
        "docentes",
        lambda f: pantalla_docentes(request, conexion, f, codigo=400))


@rutas.post("/docentes/{id}", name="modificar_docente")
async def modificar_docente(request: Request, id: str,
                            conexion=Depends(obtener_conexion),
                            usuario=Depends(requiere_administrador)):
    """Guarda los cambios de un docente."""
    editando = docentes.obtener(conexion, int(id)) if id.isdigit() else None
    return await procesar_formulario(
        request,
        lambda f: docentes.modificar(conexion, id, *_datos(f)),
        lambda d: f"Se guardaron los cambios de {d.nombre_completo}.",
        "docentes",
        lambda f: pantalla_docentes(request, conexion, f, editando, 400))


@rutas.post("/docentes/{id}/eliminar", name="eliminar_docente")
async def eliminar_docente(request: Request, id: str,
                           conexion=Depends(obtener_conexion),
                           usuario=Depends(requiere_administrador)):
    """Da de baja un docente."""
    return await procesar_formulario(
        request,
        lambda f: docentes.eliminar(conexion, id),
        lambda d: f"Se dio de baja a {d.nombre_completo}.",
        "docentes",
        lambda f: pantalla_docentes(request, conexion, codigo=400))
