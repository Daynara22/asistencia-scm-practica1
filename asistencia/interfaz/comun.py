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

from asistencia import bd
from asistencia.servicios import usuarios

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
def get_flashed_messages(contexto, with_categories=False):
    """Devuelve (y borra) los mensajes pendientes. Se usa en base.html."""
    request = contexto["request"]
    if "session" not in request.scope:      # p. ej. en una página de error
        return []
    mensajes = request.session.pop("_mensajes", [])
    if with_categories:
        return [tuple(m) for m in mensajes]
    return [m[1] for m in mensajes]


# ----------------------------------------------------------------------
# Direcciones y respuestas
# ----------------------------------------------------------------------

def ruta_de(request, nombre, **parametros):
    """
    Arma la dirección de una página por su nombre.

    ruta_de(request, 'static', filename='estilos.css', v=3)
        -> /static/estilos.css?v=3
    ruta_de(request, 'informe', dni='45123456') -> /informe?dni=45123456
    """
    if nombre == "static":
        ruta = "/static/" + parametros.pop("filename")
    else:
        ruta = request.app.url_path_for(nombre)
    return f"{ruta}?{urlencode(parametros)}" if parametros else ruta


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


templates.env.globals.update(url_for=url_for,
                             get_flashed_messages=get_flashed_messages)


def pagina(request, plantilla, estado_http=200, **contexto):
    """Muestra una plantilla con los datos comunes (usuario logueado y
    versión del CSS)."""
    contexto.setdefault("docente", getattr(request.state, "usuario", None))
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


def requiere_docente(request: Request,
                     conexion=Depends(obtener_conexion)):
    """Dependencia de las páginas protegidas: sin sesión, manda al
    login."""
    usuario = buscar_usuario(request, conexion)
    if usuario is None:
        raise NoAutenticado()
    return usuario


def iniciar_sesion(request, usuario):
    """Guarda al usuario en una sesión nueva."""
    # Sesión nueva: evita reutilizar una cookie anterior.
    request.session.clear()
    request.session["usuario_id"] = usuario.id
