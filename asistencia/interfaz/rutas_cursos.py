"""
rutas_cursos.py - Pantallas de ABM de cursos y de horarios.

Docentes y administradores ven los listados; solo los administradores
pueden dar de alta, modificar o dar de baja.
"""
from fastapi import APIRouter, Depends, Request

from asistencia.interfaz.comun import (flash, obtener_conexion, pagina,
                                       procesar_formulario,
                                       requiere_administrador,
                                       requiere_docente)
from asistencia.modelos import DIAS
from asistencia.servicios import (cursos, docentes, horarios, limites,
                                  materias)
from asistencia.validaciones import ErrorValidacion

rutas = APIRouter()


# ----------------------------------------------------------------------
# Cursos
# ----------------------------------------------------------------------

def pantalla_cursos(request, conexion, formulario=None, editando=None,
                    codigo=200):
    """Arma la pantalla de cursos (listado y formulario)."""
    return pagina(request, "cursos.html", codigo, seccion="cursos",
                  cursos=cursos.listar(conexion),
                  docentes=docentes.listar(conexion),
                  limite_general=limites.limite_general(conexion),
                  formulario=formulario or {}, editando=editando)


def _datos_curso(formulario):
    """Campos del formulario en el orden que piden los servicios."""
    return (formulario.get("nombre"), formulario.get("anio"),
            formulario.get("division"), formulario.get("docente_id"),
            formulario.get("limite_faltas"))


@rutas.get("/cursos", name="cursos")
async def lista_cursos(request: Request, editar: str = "",
                       conexion=Depends(obtener_conexion),
                       usuario=Depends(requiere_docente)):
    """Listado de cursos. Con ?editar=ID, el formulario edita ese
    curso."""
    if editar and usuario.es_administrador:
        try:
            curso = cursos.buscar(conexion, editar)
        except ErrorValidacion as error:
            flash(request, str(error), "error")
            return pantalla_cursos(request, conexion, codigo=404)
        formulario = {"nombre": curso.nombre, "anio": str(curso.anio),
                      "division": curso.division,
                      "docente_id": str(curso.docente_id),
                      "limite_faltas": str(curso.limite_faltas or "")}
        return pantalla_cursos(request, conexion, formulario, curso)
    return pantalla_cursos(request, conexion)


@rutas.post("/cursos", name="alta_curso")
async def alta_curso(request: Request, conexion=Depends(obtener_conexion),
                     usuario=Depends(requiere_administrador)):
    """Da de alta un curso."""
    return await procesar_formulario(
        request,
        lambda f: cursos.alta(conexion, *_datos_curso(f)),
        lambda c: f"Se dio de alta el curso {c.nombre_completo}.",
        "cursos",
        lambda f: pantalla_cursos(request, conexion, f, codigo=400))


@rutas.post("/cursos/{id}", name="modificar_curso")
async def modificar_curso(request: Request, id: str,
                          conexion=Depends(obtener_conexion),
                          usuario=Depends(requiere_administrador)):
    """Guarda los cambios de un curso."""
    editando = cursos.obtener(conexion, int(id)) if id.isdigit() else None
    return await procesar_formulario(
        request,
        lambda f: cursos.modificar(conexion, id, *_datos_curso(f)),
        lambda c: f"Se guardaron los cambios de {c.nombre_completo}.",
        "cursos",
        lambda f: pantalla_cursos(request, conexion, f, editando, 400))


@rutas.post("/cursos/{id}/eliminar", name="eliminar_curso")
async def eliminar_curso(request: Request, id: str,
                         conexion=Depends(obtener_conexion),
                         usuario=Depends(requiere_administrador)):
    """Da de baja un curso y sus horarios."""
    return await procesar_formulario(
        request,
        lambda f: cursos.eliminar(conexion, id),
        lambda c: f"Se dio de baja el curso {c.nombre_completo}.",
        "cursos",
        lambda f: pantalla_cursos(request, conexion, codigo=400))


# ----------------------------------------------------------------------
# Horarios
# ----------------------------------------------------------------------

def pantalla_horarios(request, conexion, formulario=None, editando=None,
                      codigo=200, curso_id=None):
    """Arma la pantalla de horarios (listado y formulario)."""
    return pagina(request, "horarios.html", codigo, seccion="horarios",
                  horarios=horarios.listar(conexion, curso_id),
                  cursos=cursos.listar(conexion),
                  materias=materias.listar(conexion), dias=DIAS,
                  filtro_curso=str(curso_id or ""),
                  formulario=formulario or {}, editando=editando)


def _datos_horario(formulario):
    """Campos del formulario en el orden que piden los servicios."""
    return (formulario.get("curso_id"), formulario.get("dia"),
            formulario.get("hora_inicio"), formulario.get("hora_fin"),
            formulario.get("materia"))


def _mensaje_horario(conexion, horario, accion):
    """'Se agregó el bloque del lunes de 08:00 a 09:20 en ...'."""
    curso = cursos.obtener(conexion, horario.curso_id)
    return (f"Se {accion} el bloque del {horario.nombre_dia.lower()} de "
            f"{horario.hora_inicio} a {horario.hora_fin} en "
            f"{curso.nombre_completo}.")


@rutas.get("/horarios", name="horarios")
async def lista_horarios(request: Request, editar: str = "",
                         curso: str = "",
                         conexion=Depends(obtener_conexion),
                         usuario=Depends(requiere_docente)):
    """
    Listado de horarios.

    Con ?curso=ID muestra solo ese curso; con ?editar=ID, el formulario
    edita ese bloque.
    """
    curso_id = int(curso) if curso.isdigit() else None
    if editar and usuario.es_administrador:
        try:
            horario = horarios.buscar(conexion, editar)
        except ErrorValidacion as error:
            flash(request, str(error), "error")
            return pantalla_horarios(request, conexion, codigo=404)
        materia = conexion.execute(
            "SELECT nombre FROM materias WHERE id = ?",
            (horario.materia_id,)).fetchone()["nombre"]
        formulario = {"curso_id": str(horario.curso_id),
                      "dia": str(horario.dia),
                      "hora_inicio": horario.hora_inicio,
                      "hora_fin": horario.hora_fin, "materia": materia}
        return pantalla_horarios(request, conexion, formulario, horario,
                                 curso_id=curso_id)
    return pantalla_horarios(request, conexion, curso_id=curso_id)


@rutas.post("/horarios", name="alta_horario")
async def alta_horario(request: Request, conexion=Depends(obtener_conexion),
                       usuario=Depends(requiere_administrador)):
    """Agrega un bloque de horario."""
    return await procesar_formulario(
        request,
        lambda f: horarios.alta(conexion, *_datos_horario(f)),
        lambda h: _mensaje_horario(conexion, h, "agregó"),
        "horarios",
        lambda f: pantalla_horarios(request, conexion, f, codigo=400))


@rutas.post("/horarios/{id}", name="modificar_horario")
async def modificar_horario(request: Request, id: str,
                            conexion=Depends(obtener_conexion),
                            usuario=Depends(requiere_administrador)):
    """Guarda los cambios de un bloque de horario."""
    editando = horarios.obtener(conexion, int(id)) if id.isdigit() else None
    return await procesar_formulario(
        request,
        lambda f: horarios.modificar(conexion, id, *_datos_horario(f)),
        lambda h: _mensaje_horario(conexion, h, "modificó"),
        "horarios",
        lambda f: pantalla_horarios(request, conexion, f, editando, 400))


@rutas.post("/horarios/{id}/eliminar", name="eliminar_horario")
async def eliminar_horario(request: Request, id: str,
                           conexion=Depends(obtener_conexion),
                           usuario=Depends(requiere_administrador)):
    """Quita un bloque de horario."""
    return await procesar_formulario(
        request,
        lambda f: horarios.eliminar(conexion, id),
        lambda h: _mensaje_horario(conexion, h, "quitó"),
        "horarios",
        lambda f: pantalla_horarios(request, conexion, codigo=400))
