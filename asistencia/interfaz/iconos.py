"""
iconos.py - Íconos SVG de la interfaz (trazo de línea, 24 x 24).

Se usan desde las plantillas con {{ icono('alumnos') }}. Son SVG en el
mismo HTML (sin archivos ni fuentes de íconos), toman el color del texto
(currentColor) y por eso cambian solos con el modo claro / oscuro.
"""
from markupsafe import Markup

TRAZOS = {
    "inicio": '<rect x="3" y="3" width="7" height="7" rx="1.5"/>'
              '<rect x="14" y="3" width="7" height="7" rx="1.5"/>'
              '<rect x="3" y="14" width="7" height="7" rx="1.5"/>'
              '<rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "asistencia": '<path d="M9 11l3 3L22 4"/>'
                  '<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 '
                  '0 1 2-2h11"/>',
    "alumnos": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
               '<circle cx="9" cy="7" r="4"/>'
               '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>'
               '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "docentes": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
                '<circle cx="9" cy="7" r="4"/>'
                '<polyline points="16 11 18 13 22 9"/>',
    "cursos": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>'
              '<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 '
              '0 0 1 6.5 2z"/>',
    "horarios": '<circle cx="12" cy="12" r="10"/>'
                '<polyline points="12 6 12 12 16 14"/>',
    "informes": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 '
                '0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>'
                '<line x1="16" y1="13" x2="8" y2="13"/>'
                '<line x1="16" y1="17" x2="8" y2="17"/>',
    "graficos": '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/>'
                '<path d="M22 12A10 10 0 0 0 12 2v10z"/>',
    "configuracion": '<line x1="4" y1="21" x2="4" y2="14"/>'
                     '<line x1="4" y1="10" x2="4" y2="3"/>'
                     '<line x1="12" y1="21" x2="12" y2="12"/>'
                     '<line x1="12" y1="8" x2="12" y2="3"/>'
                     '<line x1="20" y1="21" x2="20" y2="16"/>'
                     '<line x1="20" y1="12" x2="20" y2="3"/>'
                     '<line x1="1" y1="14" x2="7" y2="14"/>'
                     '<line x1="9" y1="8" x2="15" y2="8"/>'
                     '<line x1="17" y1="16" x2="23" y2="16"/>',
    "usuarios": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "salir": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
             '<polyline points="16 17 21 12 16 7"/>'
             '<line x1="21" y1="12" x2="9" y2="12"/>',
    "menu": '<line x1="3" y1="6" x2="21" y2="6"/>'
            '<line x1="3" y1="12" x2="21" y2="12"/>'
            '<line x1="3" y1="18" x2="21" y2="18"/>',
    "luna": '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
    "sol": '<circle cx="12" cy="12" r="5"/>'
           '<path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 '
           '1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>',
    "marca": '<polyline points="20 6 9 17 4 12"/>',
    "alerta": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 '
              '0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
              '<line x1="12" y1="9" x2="12" y2="13"/>'
              '<line x1="12" y1="17" x2="12.01" y2="17"/>',
    "superado": '<circle cx="12" cy="12" r="10"/>'
                '<line x1="15" y1="9" x2="9" y2="15"/>'
                '<line x1="9" y1="9" x2="15" y2="15"/>',
    "tendencia": '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>'
                 '<polyline points="17 6 23 6 23 12"/>',
    "editar": '<path d="M12 20h9"/>'
              '<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "borrar": '<polyline points="3 6 5 6 21 6"/>'
              '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'
              '<path d="M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 '
              '1 1v2"/>',
    "descargar": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
                 '<polyline points="7 10 12 15 17 10"/>'
                 '<line x1="12" y1="15" x2="12" y2="3"/>',
}


def icono(nombre, clase=""):
    """
    SVG del ícono pedido, listo para poner en la plantilla.

    Los íconos son decorativos (aria-hidden): el texto que los acompaña
    es el que leen los lectores de pantalla.
    """
    clases = f"icono {clase}".strip()
    return Markup(
        f'<svg class="{clases}" viewBox="0 0 24 24" aria-hidden="true" '
        f'focusable="false">{TRAZOS[nombre]}</svg>')
