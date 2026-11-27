"""
comun.py - Herramientas que comparten todas las pantallas.

Incluye: plantillas, mensajes "flash", armado de direcciones, conexión a
la base por request y control de sesión.
"""
import os
from contextlib import closing
from urllib.parse import urlencode

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from starlette.routing import NoMatchFound

from asistencia import bd
from asistencia.interfaz.iconos import icono
from asistencia.modelos import ADMINISTRADOR, ALUMNO, DOCENTE
from asistencia.servicios import usuarios
from asistencia.validaciones import ErrorValidacion

CARPETA_PROYECTO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CARPETA_ESTATICOS = os.path.join(CARPETA_PROYECTO, "static")
CARPETA_PLANTILLAS = os.path.join(CARPETA_PROYECTO, "templates")

# Relee los HTML si cambian.
templates = Jinja2Templates(directory=CARPETA_PLANTILLAS)


# ----------------------------------------------------------------------
# Mensajes en pantalla ("flash")
# ----------------------------------------------------------------------

def flash(request, mensaje, categoria="exito"):
    """Guarda un mensaje para mostrarlo en la próxima pantalla."""
    mensajes = request.session.get("_mensajes", [])
    mensajes.append([categoria, mensaje])
    # Se reasigna la lista para que la sesión se marque como modificada.
    request.session["_mensajes"] = mensajes


@pass_context
def get_flashed_messages(contexto, with_categories=True):
    """
    Devuelve (y borra) los mensajes pendientes como (categoría, texto).

    Se usa en base.html. El parámetro with_categories se acepta por
    compatibilidad con la plantilla; siempre se devuelven las categorías.
    """
    request = contexto["request"]
    if "session" not in request.scope:      # p. ej. en una página de error
        return []
    return [tuple(m) for m in request.session.pop("_mensajes", [])]


# ----------------------------------------------------------------------
# Direcciones y respuestas
# ----------------------------------------------------------------------

# Parámetros que algunas rutas llevan dentro de la dirección:
# /cursos/{id}, /informe/{formato}...
PARAMETROS_EN_RUTA = ("id", "formato")


def _armar_ruta(app, nombre, parametros):
    """
    Devuelve la dirección de la ruta y saca de 'parametros' los que usó.

    Primero prueba poniendo id/formato dentro de la dirección; si la ruta
    no los lleva, quedan para después del "?".
    """
    en_ruta = {clave: str(parametros[clave]) for clave in PARAMETROS_EN_RUTA
               if parametros.get(clave) is not None}
    if en_ruta:
        try:
            ruta = app.url_path_for(nombre, **en_ruta)
        except NoMatchFound:
            return app.url_path_for(nombre)
        for clave in en_ruta:
            parametros.pop(clave)
        return ruta
    return app.url_path_for(nombre)


def ruta_de(request, nombre, **parametros):
    """
    Arma la dirección de una página por su nombre.

    ruta_de(request, 'static', filename='estilos.css', v=3)
        -> /static/estilos.css?v=3
    ruta_de(request, 'informe', dni='45123456') -> /informe?dni=45123456
    ruta_de(request, 'modificar_curso', id=3) -> /cursos/3
    ruta_de(request, 'exportar_informe', formato='pdf', dni='45123456')
        -> /informe/pdf?dni=45123456

    Los parámetros que la ruta tiene en su dirección ({id}, {formato})
    van ahí; el resto, después del "?". Los vacíos o None se omiten.
    """
    if nombre == "static":
        ruta = "/static/" + parametros.pop("filename")
    else:
        ruta = _armar_ruta(request.app, nombre, parametros)
    consulta = {clave: valor for clave, valor in parametros.items()
                if valor is not None and valor != ""}
    return f"{ruta}?{urlencode(consulta)}" if consulta else ruta


@pass_context
def url_for(contexto, nombre, **parametros):
    """Versión de ruta_de para usar dentro de las plantillas."""
    return ruta_de(contexto["request"], nombre, **parametros)


def version_estaticos():
    """
    Número que cambia cada vez que se modifica el CSS o el JS.

    Se agrega a la dirección del archivo (?v=...) para que el navegador
    no use una copia vieja.
    """
    try:
        return int(max(
            os.path.getmtime(os.path.join(CARPETA_ESTATICOS, nombre))
            for nombre in ("estilos.css", "app.js")))
    except OSError:
        return 0


templates.env.globals.update(url_for=url_for, icono=icono,
                             get_flashed_messages=get_flashed_messages)


def pagina(request, plantilla, estado_http=200, **contexto):
    """Muestra una plantilla con los datos comunes (usuario logueado y
    versión del CSS)."""
    contexto.setdefault("usuario", getattr(request.state, "usuario", None))
    contexto["version_estaticos"] = version_estaticos()
    return templates.TemplateResponse(request, plantilla, contexto,
                                      status_code=estado_http)


def redirigir(request, nombre, **parametros):
    """Respuesta que lleva a otra página (código 302)."""
    return RedirectResponse(ruta_de(request, nombre, **parametros),
                            status_code=302)


# ----------------------------------------------------------------------
# Base de datos
# ----------------------------------------------------------------------

def obtener_conexion(request: Request):
    """
    Dependencia de FastAPI: una conexión a la base por cada request.

    Se cierra sola cuando termina el request, aunque haya un error.
    """
    with closing(bd.conectar(request.app.state.ruta_bd)) as conexion:
        yield conexion


# ----------------------------------------------------------------------
# Sesión
# ----------------------------------------------------------------------

class NoAutenticado(Exception):
    """Alguien sin sesión quiso entrar a una página protegida."""


class SinPermiso(Exception):
    """El usuario tiene sesión, pero su rol no permite entrar ahí."""


def buscar_usuario(request, conexion):
    """Busca al usuario de la sesión y lo deja en request.state.usuario
    (o None)."""
    request.state.usuario = None
    usuario_id = request.session.get("usuario_id")
    if usuario_id is not None:
        usuario = usuarios.obtener(conexion, usuario_id)
        if usuario:
            request.state.usuario = usuario
        else:
            request.session.pop("usuario_id", None)   # la cuenta ya no está
    return request.state.usuario


def buscar_usuario_sin_conexion(request):
    """
    Igual que buscar_usuario, pero abre su propia conexión.

    Se usa en las páginas de error. Si la base no responde, sigue sin
    usuario en lugar de fallar otra vez.
    """
    request.state.usuario = None
    if "session" not in request.scope:
        return None
    try:
        with closing(bd.conectar(request.app.state.ruta_bd)) as conexion:
            return buscar_usuario(request, conexion)
    except Exception:
        return None


def requiere_usuario(request: Request,
                     conexion=Depends(obtener_conexion)):
    """Dependencia de las páginas protegidas: sin sesión, manda al
    login."""
    usuario = buscar_usuario(request, conexion)
    if usuario is None:
        raise NoAutenticado()
    return usuario


def requiere_rol(*roles):
    """
    Crea una dependencia que solo deja pasar a los roles indicados.

    Uso: usuario=Depends(requiere_rol(ADMINISTRADOR))
    Sin sesión manda al login; con otro rol muestra "sin permiso" (403).
    """
    def dependencia(usuario=Depends(requiere_usuario)):
        """Revisa el rol del usuario de la sesión."""
        if usuario.rol not in roles:
            raise SinPermiso()
        return usuario
    return dependencia


# Dependencias listas para usar en las rutas.
requiere_docente = requiere_rol(ADMINISTRADOR, DOCENTE)
requiere_administrador = requiere_rol(ADMINISTRADOR)
requiere_alumno = requiere_rol(ALUMNO)


def iniciar_sesion(request, usuario):
    """Guarda al usuario en una sesión nueva."""
    # Sesión nueva: evita reutilizar una cookie anterior.
    request.session.clear()
    request.session["usuario_id"] = usuario.id


# ----------------------------------------------------------------------
# Formularios de ABM (alta, baja y modificación)
# ----------------------------------------------------------------------

async def procesar_formulario(request, accion, mensaje_exito, destino,
                              pantalla_con_error):
    """
    Pasos comunes de todos los formularios de ABM.

    1. Lee el formulario y llama a accion(formulario).
    2. Si hay un ErrorValidacion, muestra el mensaje y vuelve a la
       pantalla con lo que se había escrito: pantalla_con_error(formulario).
    3. Si sale bien, muestra mensaje_exito(resultado) y redirige a la
       página 'destino'.
    """
    formulario = await request.form()
    try:
        resultado = accion(formulario)
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        return pantalla_con_error(formulario)
    flash(request, mensaje_exito(resultado), "exito")
    return redirigir(request, destino)
