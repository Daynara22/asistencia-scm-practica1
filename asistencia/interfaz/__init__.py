"""
Interfaz web del sistema (FastAPI).

crear_app() arma la aplicación: rutas, archivos estáticos, sesión,
límite de tamaño de los envíos y páginas de error amigables.
"""
import logging
import os
import secrets
import sqlite3

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from asistencia import bd
from asistencia.interfaz import (rutas_acceso, rutas_alumnos,
                                 rutas_asistencia, rutas_cursos,
                                 rutas_docentes, rutas_usuarios)
from asistencia.interfaz.comun import (CARPETA_ESTATICOS, NoAutenticado,
                                       SinPermiso,
                                       buscar_usuario_sin_conexion, pagina,
                                       redirigir)

TAMANO_MAXIMO = 16 * 1024          # formularios chicos: máximo 16 KB

MENSAJES_ERROR = {
    403: "No tenés permiso para entrar a esta página.",
    404: "La página que buscás no existe.",
    405: "Esa acción no está permitida desde acá.",
    413: "Los datos enviados son demasiado grandes.",
}

registro_errores = logging.getLogger("asistencia")


def pagina_error(request, codigo, mensaje=None):
    """Página de error clara, nunca un error de Python en pantalla."""
    buscar_usuario_sin_conexion(request)
    mensaje = mensaje or MENSAJES_ERROR.get(
        codigo, "No se pudo completar la acción.")
    return pagina(request, "error.html", codigo, seccion=None,
                  codigo=codigo, mensaje=mensaje)


class LimiteDeTamano:
    """Middleware que rechaza con 413 los envíos más grandes que
    TAMANO_MAXIMO."""

    def __init__(self, aplicacion):
        """Envuelve a la aplicación ASGI recibida."""
        self.aplicacion = aplicacion

    async def __call__(self, scope, receive, send):
        """Revisa el tamaño declarado antes de leer el cuerpo."""
        if scope["type"] == "http":
            largo = dict(scope["headers"]).get(b"content-length", b"")
            if largo.isdigit() and int(largo) > TAMANO_MAXIMO:
                request = Request(scope)
                respuesta = pagina_error(request, 413)
                await respuesta(scope, receive, send)
                return
        await self.aplicacion(scope, receive, send)


def _registrar_manejadores_de_error(app):
    """Conecta cada tipo de error con su página."""

    @app.exception_handler(NoAutenticado)
    async def ir_al_login(request, error):
        """Sin sesión iniciada: al login."""
        return redirigir(request, "login")

    @app.exception_handler(SinPermiso)
    async def sin_permiso(request, error):
        """Con sesión, pero sin el rol necesario."""
        return pagina_error(request, 403)

    @app.exception_handler(StarletteHTTPException)
    async def error_http(request, error):
        """Errores HTTP (404, 405...)."""
        return pagina_error(request, error.status_code)

    @app.exception_handler(sqlite3.Error)
    async def error_base_de_datos(request, error):
        """La base no respondió (bloqueada, dañada o sin permisos)."""
        registro_errores.exception("Error de base de datos")
        return pagina_error(
            request, 500,
            "No se pudo acceder a la base de datos. Probá de nuevo en unos "
            "segundos.")

    @app.exception_handler(Exception)
    async def error_inesperado(request, error):
        """Cualquier otro error."""
        registro_errores.exception("Error inesperado")
        return pagina_error(request, 500,
                            "Ocurrió un error inesperado. Probá de nuevo.")


def crear_app(ruta_bd=None, clave_secreta=None):
    """
    Crea la aplicación web.

    ruta_bd: archivo de la base (por defecto, el de bd.ruta_configurada).
    clave_secreta: firma la cookie de sesión. Si no se indica, se usa la
    variable de entorno SECRET_KEY, y si tampoco existe se genera una al
    azar (en ese caso, al reiniciar el servidor hay que volver a entrar).
    """
    app = FastAPI(title="Sistema de Asistencia", docs_url=None,
                  redoc_url=None, openapi_url=None)
    app.state.ruta_bd = ruta_bd or bd.ruta_configurada()

    app.mount("/static", StaticFiles(directory=CARPETA_ESTATICOS),
              name="static")
    app.include_router(rutas_acceso.rutas)
    app.include_router(rutas_asistencia.rutas)
    app.include_router(rutas_alumnos.rutas)
    app.include_router(rutas_usuarios.rutas)
    app.include_router(rutas_docentes.rutas)
    app.include_router(rutas_cursos.rutas)
    _registrar_manejadores_de_error(app)

    # El orden importa: la sesión tiene que envolver a todo lo demás.
    app.add_middleware(LimiteDeTamano)
    app.add_middleware(
        SessionMiddleware,
        secret_key=(clave_secreta or os.environ.get("SECRET_KEY")
                    or secrets.token_hex(32)),
        same_site="lax",
        max_age=None,          # la sesión dura hasta cerrar el navegador
    )
    return app
