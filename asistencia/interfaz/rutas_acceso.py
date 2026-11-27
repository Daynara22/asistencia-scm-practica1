"""rutas_acceso.py - Login, creación de cuenta y cierre de sesión."""
from fastapi import APIRouter, Depends, Request

from asistencia.interfaz.comun import (buscar_usuario, flash,
                                       iniciar_sesion, obtener_conexion,
                                       pagina, redirigir)
from asistencia.servicios import usuarios
from asistencia.validaciones import ErrorValidacion

rutas = APIRouter()


@rutas.api_route("/login", methods=["GET", "POST"], name="login")
async def login(request: Request, conexion=Depends(obtener_conexion)):
    """Pantalla de ingreso con email y contraseña."""
    if buscar_usuario(request, conexion):
        return redirigir(request, "dashboard")

    email = ""
    if request.method == "POST":
        formulario = await request.form()
        email = formulario.get("email", "")
        try:
            usuario = usuarios.autenticar(conexion, email,
                                          formulario.get("clave"))
        except ErrorValidacion as error:
            flash(request, str(error), "error")
            return pagina(request, "login.html", 400, seccion="login",
                          email=email)
        iniciar_sesion(request, usuario)
        return redirigir(request, "dashboard")

    return pagina(request, "login.html", seccion="login", email=email)


@rutas.api_route("/registro-docente", methods=["GET", "POST"],
                 name="registro_docente")
async def registro_docente(request: Request,
                           conexion=Depends(obtener_conexion)):
    """Pantalla para que un docente cree su cuenta."""
    if buscar_usuario(request, conexion):
        return redirigir(request, "dashboard")

    formulario = {}
    if request.method == "POST":
        formulario = await request.form()
        try:
            usuario = usuarios.registrar_docente(
                conexion,
                formulario.get("email"),
                formulario.get("nombre"),
                formulario.get("apellido"),
                formulario.get("clave"),
                formulario.get("clave_repetida"),
            )
        except ErrorValidacion as error:
            flash(request, str(error), "error")
            return pagina(request, "registro_docente.html", 400,
                          seccion="login", formulario=formulario)
        iniciar_sesion(request, usuario)
        return redirigir(request, "dashboard")

    return pagina(request, "registro_docente.html", seccion="login",
                  formulario=formulario)


@rutas.post("/logout", name="logout")
async def logout(request: Request):
    """Cierra la sesión y vuelve al login."""
    request.session.clear()
    flash(request, "Cerraste la sesión.", "exito")
    return redirigir(request, "login")
