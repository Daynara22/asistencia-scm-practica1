"""
rutas_limites.py - Configuración del límite de faltas.

Docentes y administradores ven la configuración; solo los
administradores la cambian. El límite propio de cada curso se edita en
la pantalla de Cursos.
"""
from fastapi import APIRouter, Depends, Request

from asistencia.interfaz.comun import (obtener_conexion, pagina,
                                       procesar_formulario,
                                       requiere_administrador,
                                       requiere_docente)
from asistencia.servicios import cursos, limites

rutas = APIRouter()


def pantalla_limites(request, conexion, formulario=None, codigo=200):
    """Arma la pantalla del límite de faltas."""
    formulario = formulario or {
        "limite_faltas": str(limites.limite_general(conexion)),
        "valor_tardanza": limites.valor_tardanza(conexion),
    }
    return pagina(request, "limites.html", codigo, seccion="limites",
                  formulario=formulario,
                  valores_tardanza=limites.VALORES_TARDANZA,
                  umbral=round(float(limites.UMBRAL_ALERTA) * 100),
                  cursos=cursos.listar(conexion),
                  limite_general=limites.limite_general(conexion),
                  alertas=limites.alumnos_con_alerta(conexion))


@rutas.get("/limites", name="limites")
async def ver_limites(request: Request, conexion=Depends(obtener_conexion),
                      usuario=Depends(requiere_docente)):
    """Límite general, valor de la tardanza y alumnos con alerta."""
    return pantalla_limites(request, conexion)


@rutas.post("/limites", name="guardar_limites")
async def guardar_limites(request: Request,
                          conexion=Depends(obtener_conexion),
                          usuario=Depends(requiere_administrador)):
    """Guarda el límite general y el valor de la tardanza."""
    return await procesar_formulario(
        request,
        lambda f: limites.cambiar_configuracion(
            conexion, f.get("limite_faltas"), f.get("valor_tardanza")),
        lambda r: (f"Límite general: {r[0]} faltas. "
                   f"{limites.VALORES_TARDANZA[r[1]]}."),
        "limites",
        lambda f: pantalla_limites(request, conexion, f, 400))
