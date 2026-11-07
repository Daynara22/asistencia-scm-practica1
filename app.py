"""
app.py - Rutas de FastAPI (la parte web del sistema).

Este archivo solo recibe los datos de los formularios, llama a logica.py
y muestra el resultado. Las reglas y validaciones están en logica.py.

Ejecutar:  python app.py   y abrir  http://127.0.0.1:5000
"""
import logging
import os
import secrets
from datetime import date, datetime
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

import datos as almacen
import logica
from logica import ErrorValidacion

CARPETA = os.path.dirname(os.path.abspath(__file__))
CARPETA_ESTATICOS = os.path.join(CARPETA, "static")
TAMANO_MAXIMO = 16 * 1024          # formularios chicos: máximo 16 KB

app = FastAPI(title="Sistema de Asistencia", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=CARPETA_ESTATICOS), name="static")
templates = Jinja2Templates(directory=os.path.join(CARPETA, "templates"))   # relee los HTML si cambian


# ----------------------------------------------------------------------
# Mensajes en pantalla ("flash") y ayudas para las plantillas
# ----------------------------------------------------------------------

def flash(request, mensaje, categoria="exito"):
    """Guarda un mensaje para mostrarlo en la próxima pantalla."""
    request.session.setdefault("_mensajes", []).append([categoria, mensaje])
    request.session["_mensajes"] = request.session["_mensajes"]   # marca la sesión como modificada


@pass_context
def get_flashed_messages(contexto, with_categories=False):
    """Devuelve (y borra) los mensajes pendientes. Se usa desde base.html."""
    request = contexto["request"]
    if "session" not in request.scope:      # p. ej. en la página de error 500
        return []
    mensajes = request.session.pop("_mensajes", [])
    return [tuple(m) for m in mensajes] if with_categories else [m[1] for m in mensajes]


def url_for(nombre, **parametros):
    """
    Arma la dirección de una página por su nombre.
    url_for('static', filename='estilos.css', v=3) -> /static/estilos.css?v=3
    url_for('informe', dni='45123456')             -> /informe?dni=45123456
    """
    if nombre == "static":
        ruta = "/static/" + parametros.pop("filename")
    else:
        ruta = app.url_path_for(nombre)
    return f"{ruta}?{urlencode(parametros)}" if parametros else ruta


def version_estaticos():
    """
    Número que cambia cada vez que se modifica el CSS o el JS. Se agrega a la
    dirección del archivo (?v=...) para que el navegador no use una copia vieja.
    """
    try:
        return int(max(os.path.getmtime(os.path.join(CARPETA_ESTATICOS, nombre))
                       for nombre in ("estilos.css", "app.js")))
    except OSError:
        return 0


templates.env.globals.update(url_for=url_for, get_flashed_messages=get_flashed_messages)


def pagina(request, plantilla, estado_http=200, **contexto):
    """Muestra una plantilla con los datos comunes (docente logueado, versión del CSS)."""
    contexto.setdefault("docente", getattr(request.state, "docente", None))
    contexto["version_estaticos"] = version_estaticos()
    return templates.TemplateResponse(request, plantilla, contexto, status_code=estado_http)


def redirigir(nombre):
    return RedirectResponse(url_for(nombre), status_code=302)


def leer_datos(request):
    """Lee el JSON. Si estaba dañado, muestra el aviso en pantalla."""
    datos, aviso = almacen.cargar()
    if aviso:
        flash(request, aviso, "aviso")
    return datos


def guardar_datos(request, datos):
    """Guarda el JSON. Devuelve True si salió bien; si no, muestra un error."""
    try:
        almacen.guardar(datos)
        return True
    except OSError:
        flash(request, "No se pudieron guardar los cambios en el archivo. "
                       "Revisá los permisos de la carpeta «datos».", "error")
        return False


# ----------------------------------------------------------------------
# Login de docentes
# ----------------------------------------------------------------------

class NoAutenticado(Exception):
    """Se lanza cuando alguien sin sesión quiere entrar a una página protegida."""


def buscar_docente(request):
    """Busca al docente de la sesión y lo deja en request.state.docente (o None)."""
    request.state.docente = None
    email = request.session.get("docente")
    if email:
        docente = leer_datos(request)["docentes"].get(email)
        if docente:
            request.state.docente = {"email": email, **docente}
        else:
            request.session.pop("docente", None)   # la cuenta ya no existe
    return request.state.docente


def requiere_docente(request: Request):
    """Dependencia de las páginas protegidas: sin sesión iniciada, manda al login."""
    docente = buscar_docente(request)
    if docente is None:
        raise NoAutenticado()
    return docente


@app.exception_handler(NoAutenticado)
async def ir_al_login(request, error):
    return redirigir("login")


def iniciar_sesion(request, email):
    request.session.clear()            # sesión nueva: evita reutilizar una cookie anterior
    request.session["docente"] = email


@app.api_route("/login", methods=["GET", "POST"], name="login")
async def login(request: Request):
    if buscar_docente(request):
        return redirigir("dashboard")

    datos = leer_datos(request)   # además avisa si el archivo estaba dañado
    email = ""
    if request.method == "POST":
        formulario = await request.form()
        email = formulario.get("email", "")
        try:
            email, _ = logica.autenticar_docente(datos, email, formulario.get("clave"))
        except ErrorValidacion as error:
            flash(request, str(error), "error")
            return pagina(request, "login.html", 400, seccion="login", email=email)
        iniciar_sesion(request, email)
        return redirigir("dashboard")

    return pagina(request, "login.html", seccion="login", email=email)


@app.api_route("/registro-docente", methods=["GET", "POST"], name="registro_docente")
async def registro_docente(request: Request):
    if buscar_docente(request):
        return redirigir("dashboard")

    formulario = {}
    if request.method == "POST":
        formulario = await request.form()
        datos = leer_datos(request)
        try:
            email, _ = logica.registrar_docente(
                datos,
                formulario.get("email"),
                formulario.get("nombre"),
                formulario.get("apellido"),
                formulario.get("clave"),
                formulario.get("clave_repetida"),
            )
        except ErrorValidacion as error:
            flash(request, str(error), "error")
            return pagina(request, "registro_docente.html", 400, seccion="login", formulario=formulario)
        if guardar_datos(request, datos):
            iniciar_sesion(request, email)
            return redirigir("dashboard")

    return pagina(request, "registro_docente.html", seccion="login", formulario=formulario)


@app.post("/logout", name="logout")
async def logout(request: Request):
    request.session.clear()
    flash(request, "Cerraste la sesión.", "exito")
    return redirigir("login")


# ----------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------

@app.get("/", name="dashboard")
async def dashboard(request: Request, docente=Depends(requiere_docente)):
    datos = leer_datos(request)
    hoy = date.today()
    return pagina(
        request, "dashboard.html",
        seccion="dashboard",
        fecha_texto=hoy.strftime("%d/%m/%Y"),
        hora_limite=datos["config"]["hora_limite"],
        cerrado=logica.dia_cerrado(datos, hoy),
        resumen=logica.resumen_general(datos, hoy),
    )


# ----------------------------------------------------------------------
# Registrar asistencia
# ----------------------------------------------------------------------

def pantalla_registro(request, datos, formulario_manual=None, codigo=200):
    """Arma la pantalla de Registrar asistencia."""
    hoy = date.today()
    return pagina(
        request, "index.html", codigo,
        seccion="registro",
        fecha_texto=hoy.strftime("%d/%m/%Y"),
        hoy_iso=hoy.isoformat(),
        hora_actual=datetime.now().strftime("%H:%M"),
        hora_limite=datos["config"]["hora_limite"],
        cerrado=logica.dia_cerrado(datos, hoy),
        resumen=logica.resumen_del_dia(datos, hoy),
        ultimo=request.session.pop("ultimo_registro", None),
        manual=formulario_manual or {},
    )


@app.get("/asistencia", name="asistencia")
async def asistencia(request: Request, docente=Depends(requiere_docente)):
    return pantalla_registro(request, leer_datos(request))


@app.post("/registrar", name="registrar")
async def registrar(request: Request, docente=Depends(requiere_docente)):
    formulario = await request.form()
    datos = leer_datos(request)
    try:
        resultado = logica.registrar_asistencia(datos, formulario.get("dni"))
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        return pantalla_registro(request, datos, codigo=400)

    if guardar_datos(request, datos):
        request.session["ultimo_registro"] = resultado
    return redirigir("asistencia")


@app.post("/hora-limite", name="hora_limite")
async def hora_limite(request: Request, docente=Depends(requiere_docente)):
    formulario = await request.form()
    datos = leer_datos(request)
    try:
        nueva = logica.cambiar_hora_limite(datos, formulario.get("hora_limite"))
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        return pantalla_registro(request, datos, codigo=400)

    if guardar_datos(request, datos):
        flash(request, f"Hora límite actualizada a las {nueva}.", "exito")
    return redirigir("asistencia")


@app.post("/cerrar-dia", name="cerrar_dia")
async def cerrar_dia(request: Request, docente=Depends(requiere_docente)):
    datos = leer_datos(request)
    try:
        marcados = logica.cerrar_dia(datos)
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        return pantalla_registro(request, datos, codigo=400)

    if guardar_datos(request, datos):
        if marcados == 1:
            flash(request, "Día cerrado. Se marcó 1 alumno como AUSENTE.", "exito")
        else:
            flash(request, f"Día cerrado. Se marcaron {marcados} alumnos como AUSENTE.", "exito")
    return redirigir("asistencia")


@app.post("/manual", name="carga_manual")
async def carga_manual(request: Request, docente=Depends(requiere_docente)):
    formulario = await request.form()
    datos = leer_datos(request)
    try:
        resultado = logica.carga_manual(
            datos,
            formulario.get("dni"),
            formulario.get("fecha"),
            formulario.get("estado"),
            formulario.get("hora"),
        )
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        return pantalla_registro(request, datos, formulario_manual=formulario, codigo=400)

    if guardar_datos(request, datos):
        fecha = datetime.strptime(resultado["fecha"], "%Y-%m-%d").strftime("%d/%m/%Y")
        detalle = f" a las {resultado['hora']}" if resultado["hora"] else ""
        flash(request, f"Se cargó {resultado['estado']} para {resultado['nombre']} el {fecha}{detalle}.", "exito")
    return redirigir("asistencia")


# ----------------------------------------------------------------------
# Alumnos
# ----------------------------------------------------------------------

@app.api_route("/alumnos", methods=["GET", "POST"], name="alumnos")
async def alumnos(request: Request, docente=Depends(requiere_docente)):
    datos = leer_datos(request)
    formulario = {}

    if request.method == "POST":
        formulario = await request.form()
        try:
            alumno = logica.alta_alumno(
                datos, formulario.get("dni"), formulario.get("nombre"), formulario.get("apellido"))
        except ErrorValidacion as error:
            flash(request, str(error), "error")
        else:
            if guardar_datos(request, datos):
                flash(request, f"Se dio de alta a {logica.nombre_completo(alumno)}.", "exito")
            return redirigir("alumnos")

    lista = logica.listar_alumnos(datos)
    for alumno in lista:
        try:
            alumno["porcentaje"] = logica.informe_alumno(datos, alumno["dni"])["porcentaje_asistencia"]
        except ErrorValidacion:
            alumno["porcentaje"] = None
    codigo = 400 if request.method == "POST" else 200
    return pagina(request, "alumnos.html", codigo, seccion="alumnos", alumnos=lista, formulario=formulario)


# ----------------------------------------------------------------------
# Informe
# ----------------------------------------------------------------------

@app.get("/informe", name="informe")
async def informe(request: Request, dni: str = "", docente=Depends(requiere_docente)):
    datos = leer_datos(request)
    dni = dni.strip()
    resultado = None
    codigo = 200

    if dni:
        try:
            resultado = logica.informe_alumno(datos, dni)
        except ErrorValidacion as error:
            flash(request, str(error), "error")
            codigo = 400

    return pagina(request, "informe.html", codigo, seccion="informe", dni=dni, informe=resultado)


# ----------------------------------------------------------------------
# Errores: siempre una página clara, nunca un error de Python en pantalla
# ----------------------------------------------------------------------

MENSAJES_ERROR = {
    404: "La página que buscás no existe.",
    405: "Esa acción no está permitida desde acá.",
    413: "Los datos enviados son demasiado grandes.",
}


def pagina_error(request, codigo, mensaje=None):
    if "session" in request.scope:
        buscar_docente(request)
    mensaje = mensaje or MENSAJES_ERROR.get(codigo, "No se pudo completar la acción.")
    return pagina(request, "error.html", codigo, seccion=None, codigo=codigo, mensaje=mensaje)


@app.exception_handler(StarletteHTTPException)
async def error_http(request, error):
    return pagina_error(request, error.status_code)


@app.exception_handler(Exception)
async def error_inesperado(request, error):
    logging.getLogger("asistencia").exception("Error inesperado")
    return pagina_error(request, 500, "Ocurrió un error inesperado. Probá de nuevo.")


class LimiteDeTamano:
    """Rechaza con 413 los envíos más grandes que TAMANO_MAXIMO."""

    def __init__(self, aplicacion):
        self.aplicacion = aplicacion

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            largo = dict(scope["headers"]).get(b"content-length", b"")
            if largo.isdigit() and int(largo) > TAMANO_MAXIMO:
                respuesta = pagina_error(Request(scope), 413)
                await respuesta(scope, receive, send)
                return
        await self.aplicacion(scope, receive, send)


# El orden importa: la sesión tiene que envolver a todo lo demás.
app.add_middleware(LimiteDeTamano)
# La clave firma la cookie de sesión (login y mensajes). Si no se define la
# variable de entorno SECRET_KEY, se genera una al azar en cada arranque
# (en ese caso, al reiniciar el servidor los docentes deben volver a entrar).
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    same_site="lax",
    max_age=None,          # la sesión dura hasta cerrar el navegador
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
