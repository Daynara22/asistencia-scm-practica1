"""
rutas_usuarios.py - Gestión de cuentas de usuario (solo administradores).

Permite ver todas las cuentas, cambiar el rol entre docente y
administrador, y crear cuentas para que los alumnos vean su asistencia.
"""
from fastapi import APIRouter, Depends, Request

from asistencia.interfaz.comun import (flash, obtener_conexion, pagina,
                                       redirigir, requiere_administrador)
from asistencia.modelos import ADMINISTRADOR
from asistencia.servicios import alumnos, usuarios
from asistencia.validaciones import ErrorValidacion

rutas = APIRouter()


def pantalla_usuarios(request, conexion, formulario=None, codigo=200):
    """Arma la pantalla de usuarios."""
    return pagina(request, "usuarios.html", codigo, seccion="usuarios",
                  cuentas=usuarios.listar(conexion),
                  alumnos=alumnos.listar(conexion),
                  formulario=formulario or {})


@rutas.get("/usuarios", name="usuarios")
async def lista_usuarios(request: Request,
                         conexion=Depends(obtener_conexion),
                         usuario=Depends(requiere_administrador)):
    """Listado de cuentas y formulario de cuenta de alumno."""
    return pantalla_usuarios(request, conexion)


@rutas.post("/usuarios/rol", name="cambiar_rol")
async def cambiar_rol(request: Request, conexion=Depends(obtener_conexion),
                      usuario=Depends(requiere_administrador)):
    """Pasa una cuenta de docente a administrador o al revés."""
    formulario = await request.form()
    try:
        cambiado = usuarios.cambiar_rol(conexion, formulario.get("usuario_id"),
                                        formulario.get("rol"))
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        return pantalla_usuarios(request, conexion, codigo=400)

    nombre_rol = usuarios.NOMBRES_DE_ROL[cambiado.rol].lower()
    flash(request, f"{cambiado.nombre_completo} ahora es {nombre_rol}.",
          "exito")
    if cambiado.id == usuario.id and cambiado.rol != ADMINISTRADOR:
        # Se quitó a sí mismo el rol: ya no puede ver esta pantalla.
        return redirigir(request, "dashboard")
    return redirigir(request, "usuarios")


@rutas.post("/usuarios/alumno", name="cuenta_alumno")
async def cuenta_alumno(request: Request,
                        conexion=Depends(obtener_conexion),
                        usuario=Depends(requiere_administrador)):
    """Crea la cuenta de un alumno para que vea su asistencia."""
    formulario = await request.form()
    try:
        cuenta = usuarios.crear_cuenta_alumno(
            conexion,
            formulario.get("dni"),
            formulario.get("email"),
            formulario.get("clave"),
            formulario.get("clave_repetida"),
        )
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        return pantalla_usuarios(request, conexion, formulario, 400)
    flash(request, f"Se creó la cuenta de {cuenta.nombre_completo}.",
          "exito")
    return redirigir(request, "usuarios")
