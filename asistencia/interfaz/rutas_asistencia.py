"""
rutas_asistencia.py - Dashboard y pantalla de registro de asistencia.

Incluye el registro por DNI, la hora límite, el cierre del día y la carga
manual.
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, Request

from asistencia.interfaz.comun import (flash, obtener_conexion, pagina,
                                       redirigir, requiere_docente,
                                       requiere_usuario)
from asistencia.servicios import (asistencias, configuracion, informes,
                                  limites)
from asistencia.validaciones import ErrorValidacion

rutas = APIRouter()


@rutas.get("/", name="dashboard")
async def dashboard(request: Request, conexion=Depends(obtener_conexion),
                    usuario=Depends(requiere_usuario)):
    """
    Pantalla de inicio con el resumen del día y el gráfico.

    Los alumnos no ven el dashboard: su inicio es su propio informe.
    """
    if usuario.es_alumno:
        return redirigir(request, "mi_asistencia")
    hoy = date.today()
    return pagina(
        request, "dashboard.html",
        seccion="dashboard",
        fecha_texto=hoy.strftime("%d/%m/%Y"),
        hora_limite=configuracion.texto_hora_limite(conexion),
        cerrado=asistencias.dia_cerrado(conexion, hoy),
        resumen=informes.resumen_general(conexion, hoy),
        alertas=limites.alumnos_con_alerta(conexion),
        limite_general=limites.limite_general(conexion),
    )


def pantalla_registro(request, conexion, formulario_manual=None,
                      codigo=200):
    """Arma la pantalla de Registrar asistencia."""
    hoy = date.today()
    return pagina(
        request, "index.html", codigo,
        seccion="registro",
        fecha_texto=hoy.strftime("%d/%m/%Y"),
        hoy_iso=hoy.isoformat(),
        hora_actual=datetime.now().strftime("%H:%M"),
        hora_limite=configuracion.texto_hora_limite(conexion),
        cerrado=asistencias.dia_cerrado(conexion, hoy),
        resumen=asistencias.resumen_del_dia(conexion, hoy),
        ultimo=request.session.pop("ultimo_registro", None),
        manual=formulario_manual or {},
    )


@rutas.get("/asistencia", name="asistencia")
async def asistencia(request: Request, conexion=Depends(obtener_conexion),
                     usuario=Depends(requiere_docente)):
    """Pantalla de Registrar asistencia."""
    return pantalla_registro(request, conexion)


@rutas.post("/registrar", name="registrar")
async def registrar(request: Request, conexion=Depends(obtener_conexion),
                    usuario=Depends(requiere_docente)):
    """Registra la llegada de un alumno por su DNI."""
    formulario = await request.form()
    try:
        resultado = asistencias.registrar(conexion, formulario.get("dni"))
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        return pantalla_registro(request, conexion, codigo=400)
    request.session["ultimo_registro"] = resultado
    return redirigir(request, "asistencia")


@rutas.post("/hora-limite", name="hora_limite")
async def hora_limite(request: Request, conexion=Depends(obtener_conexion),
                      usuario=Depends(requiere_docente)):
    """Cambia la hora límite para llegar a tiempo."""
    formulario = await request.form()
    try:
        nueva = configuracion.cambiar_hora_limite(
            conexion, formulario.get("hora_limite"))
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        return pantalla_registro(request, conexion, codigo=400)
    flash(request, f"Hora límite actualizada a las {nueva}.", "exito")
    return redirigir(request, "asistencia")


@rutas.post("/cerrar-dia", name="cerrar_dia")
async def cerrar_dia(request: Request, conexion=Depends(obtener_conexion),
                     usuario=Depends(requiere_docente)):
    """Cierra el día: marca AUSENTE a quienes no se registraron."""
    try:
        marcados = asistencias.cerrar_dia(conexion)
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        return pantalla_registro(request, conexion, codigo=400)
    if marcados == 1:
        mensaje = "Día cerrado. Se marcó 1 alumno como AUSENTE."
    else:
        mensaje = (f"Día cerrado. Se marcaron {marcados} alumnos como "
                   "AUSENTE.")
    flash(request, mensaje, "exito")
    return redirigir(request, "asistencia")


@rutas.post("/manual", name="carga_manual")
async def carga_manual(request: Request,
                       conexion=Depends(obtener_conexion),
                       usuario=Depends(requiere_docente)):
    """Carga a mano una tardanza o una ausencia."""
    formulario = await request.form()
    try:
        resultado = asistencias.carga_manual(
            conexion,
            formulario.get("dni"),
            formulario.get("fecha"),
            formulario.get("estado"),
            formulario.get("hora"),
        )
    except ErrorValidacion as error:
        flash(request, str(error), "error")
        return pantalla_registro(request, conexion,
                                 formulario_manual=formulario, codigo=400)

    fecha = datetime.strptime(resultado["fecha"], "%Y-%m-%d")
    detalle = f" a las {resultado['hora']}" if resultado["hora"] else ""
    flash(request,
          f"Se cargó {resultado['estado']} para {resultado['nombre']} el "
          f"{fecha.strftime('%d/%m/%Y')}{detalle}.", "exito")
    return redirigir(request, "asistencia")
