"""
exportar.py - Exportación de los informes a CSV y PDF.

Recibe los diccionarios que arma servicios/informes.py y devuelve el
contenido del archivo. No sabe nada de la web: las rutas solo lo envían.

- CSV: separado por punto y coma, con decimales con coma y con marca
  UTF-8 (BOM), para que Excel en español lo abra con columnas y tildes
  bien.
- PDF: con fpdf2 y la fuente Helvetica. Esa fuente solo tiene los
  caracteres latin-1 (incluye tildes, ñ y °); cualquier otro carácter se
  reemplaza por uno parecido.
"""
import csv
import io
from datetime import datetime

from fpdf import FPDF

ESTADOS_LIMITE = {"normal": "Normal", "cerca": "Cerca del límite",
                  "superado": "Superó el límite"}
REEMPLAZOS_PDF = {"—": "-", "–": "-", "→": "->", "·": "-", "…": "...",
                  "“": '"', "”": '"', "‘": "'", "’": "'"}


# ----------------------------------------------------------------------
# CSV
# ----------------------------------------------------------------------

def _decimal(numero):
    """75.0 -> '75,0' (coma decimal, como espera Excel en español)."""
    return str(numero).replace(".", ",")


def _csv(filas):
    """Arma el texto CSV (con BOM) a partir de una lista de filas."""
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    escritor.writerows(filas)
    return "﻿" + salida.getvalue()


def csv_alumno(informe):
    """CSV del informe de un alumno: resumen y detalle por fecha."""
    s = informe["situacion"]
    filas = [
        ["Informe de asistencia"],
        ["Alumno", informe["nombre"]],
        ["DNI", informe["dni"]],
        ["Curso", informe["curso"] or "Sin curso"],
        ["Período", informe["periodo"]],
        [],
        ["Presentes", "Tardanzas", "Ausentes", "Días registrados",
         "% asistencia", "Faltas", "Límite", "Estado"],
        [informe["presentes"], informe["tardanzas"], informe["ausentes"],
         informe["total"], _decimal(informe["porcentaje_asistencia"]),
         _decimal(s["faltas_texto"]), s["limite"],
         ESTADOS_LIMITE[s["estado"]]],
        [],
        ["Fecha", "Estado", "Hora", "Carga"],
    ]
    for d in informe["detalle"]:
        filas.append([d["fecha_mostrar"], d["estado"], d["hora"] or "",
                      "Manual" if d["manual"] else "Automática"])
    return _csv(filas)


def csv_total(informe):
    """CSV del informe total: resumen por curso y una fila por alumno."""
    filas = [
        ["Informe total de asistencia"],
        ["Período", informe["periodo"]],
        ["Curso", informe["curso"] or "Todos"],
        [],
        ["Curso", "Alumnos", "Presentes", "Tardanzas", "Ausentes",
         "% asistencia", "Cerca del límite", "Superaron el límite"],
    ]
    for grupo in informe["cursos"] + [informe["general"]]:
        filas.append([grupo["nombre"], grupo["alumnos"], grupo["presentes"],
                      grupo["tardanzas"], grupo["ausentes"],
                      _decimal(grupo["porcentaje_asistencia"]),
                      grupo["cerca"], grupo["superados"]])
    filas += [[], ["DNI", "Alumno", "Curso", "Presentes", "Tardanzas",
                   "Ausentes", "% asistencia", "Faltas", "Límite",
                   "Estado"]]
    for a in informe["alumnos"]:
        s = a["situacion"]
        filas.append([a["dni"], a["nombre"], a["curso"], a["presentes"],
                      a["tardanzas"], a["ausentes"],
                      _decimal(a["porcentaje_asistencia"]),
                      _decimal(s["faltas_texto"]), s["limite"],
                      ESTADOS_LIMITE[s["estado"]]])
    return _csv(filas)


# ----------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------

def _texto_pdf(valor):
    """Deja el texto con caracteres que la fuente Helvetica puede
    mostrar."""
    texto = str(valor)
    for original, reemplazo in REEMPLAZOS_PDF.items():
        texto = texto.replace(original, reemplazo)
    return texto.encode("latin-1", "replace").decode("latin-1")


class InformePDF(FPDF):
    """Hoja A4 con título, pie con fecha y número de página, y tablas."""

    def __init__(self, titulo):
        """Prepara la hoja A4 vertical con el título del informe."""
        super().__init__(orientation="P", unit="mm", format="A4")
        self.titulo = _texto_pdf(titulo)
        self.generado = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.set_auto_page_break(auto=True, margin=15)
        self.set_title(self.titulo)
        self.add_page()

    def header(self):
        """Encabezado de cada página."""
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 9, self.titulo, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(79, 91, 213)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin,
                  self.get_y())
        self.ln(4)

    def footer(self):
        """Pie de cada página: sistema, fecha y número de página."""
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(110)
        self.cell(0, 6, _texto_pdf(
            f"Sistema de Asistencia - generado el {self.generado} - "
            f"página {self.page_no()}/{{nb}}"), align="C")
        self.set_text_color(0)

    def datos(self, pares):
        """Líneas 'Etiqueta: valor' debajo del título."""
        for etiqueta, valor in pares:
            self.set_font("Helvetica", "B", 10)
            self.cell(32, 6, _texto_pdf(f"{etiqueta}:"))
            self.set_font("Helvetica", "", 10)
            self.cell(0, 6, _texto_pdf(valor), new_x="LMARGIN",
                      new_y="NEXT")
        self.ln(3)

    def subtitulo(self, texto):
        """Título de una sección."""
        self.ln(2)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 8, _texto_pdf(texto), new_x="LMARGIN", new_y="NEXT")

    def tabla(self, encabezados, filas, anchos):
        """Tabla simple con encabezado sombreado y filas alternadas."""
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(236, 238, 252)
        for texto, ancho in zip(encabezados, anchos):
            self.cell(ancho, 7, _texto_pdf(texto), border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 9)
        for numero, fila in enumerate(filas):
            self.set_fill_color(248, 249, 253)
            for valor, ancho in zip(fila, anchos):
                self.cell(ancho, 6, _texto_pdf(valor), border=1,
                          fill=numero % 2 == 1)
            self.ln()

    def barra(self, presentes, tardanzas, ausentes):
        """Gráfico de barra horizontal con los porcentajes."""
        ancho_total = self.w - self.l_margin - self.r_margin
        x, y = self.l_margin, self.get_y()
        colores = ((22, 163, 74), (217, 119, 6), (220, 38, 38))
        for valor, color in zip((presentes, tardanzas, ausentes), colores):
            ancho = ancho_total * valor / 100
            if ancho > 0:
                self.set_fill_color(*color)
                self.rect(x, y, ancho, 5, style="F")
                x += ancho
        self.ln(7)
        self.set_font("Helvetica", "", 8)
        self.cell(0, 5, _texto_pdf(
            f"Presentes {presentes} %   Tardanzas {tardanzas} %   "
            f"Ausentes {ausentes} %"), new_x="LMARGIN", new_y="NEXT")


def pdf_alumno(informe):
    """PDF del informe de un alumno. Devuelve los bytes del archivo."""
    s = informe["situacion"]
    pdf = InformePDF("Informe de asistencia")
    pdf.datos([("Alumno", informe["nombre"]), ("DNI", informe["dni"]),
               ("Curso", informe["curso"] or "Sin curso"),
               ("Período", informe["periodo"])])
    pdf.tabla(["Presentes", "Tardanzas", "Ausentes", "Días",
               "% asistencia", "Faltas / límite"],
              [[informe["presentes"], informe["tardanzas"],
                informe["ausentes"], informe["total"],
                f"{informe['porcentaje_asistencia']} %",
                f"{s['faltas_texto']} / {s['limite']}"]],
              [28, 28, 28, 22, 34, 40])
    pdf.ln(3)
    if informe["total"]:
        pdf.barra(informe["porcentaje_presentes"],
                  informe["porcentaje_tardanzas"],
                  informe["porcentaje_ausentes"])
    if s["mensaje"]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(185, 28, 28)
        pdf.multi_cell(0, 6, _texto_pdf(s["mensaje"]))
        pdf.set_text_color(0)

    pdf.subtitulo("Detalle por fecha")
    if informe["detalle"]:
        pdf.tabla(["Fecha", "Estado", "Hora", "Carga"],
                  [[d["fecha_mostrar"], d["estado"], d["hora"] or "-",
                    "Manual" if d["manual"] else "Automática"]
                   for d in informe["detalle"]],
                  [40, 45, 30, 45])
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "No hay registros en el período.")
    return bytes(pdf.output())


def pdf_total(informe):
    """PDF del informe total. Devuelve los bytes del archivo."""
    pdf = InformePDF("Informe total de asistencia")
    pdf.datos([("Período", informe["periodo"]),
               ("Curso", informe["curso"] or "Todos")])

    general = informe["general"]
    pdf.subtitulo("Resumen general")
    pdf.tabla(["Alumnos", "Presentes", "Tardanzas", "Ausentes",
               "% asistencia", "Cerca", "Superaron"],
              [[general["alumnos"], general["presentes"],
                general["tardanzas"], general["ausentes"],
                f"{general['porcentaje_asistencia']} %", general["cerca"],
                general["superados"]]],
              [24, 26, 26, 26, 30, 22, 26])
    pdf.ln(2)
    if general["total"]:
        pdf.barra(general["porcentaje_presentes"],
                  general["porcentaje_tardanzas"],
                  general["porcentaje_ausentes"])

    pdf.subtitulo("Por curso")
    pdf.tabla(["Curso", "Alumnos", "Pres.", "Tard.", "Aus.", "% asist.",
               "Alertas"],
              [[g["nombre"], g["alumnos"], g["presentes"], g["tardanzas"],
                g["ausentes"], f"{g['porcentaje_asistencia']} %",
                g["cerca"] + g["superados"]] for g in informe["cursos"]],
              [62, 18, 16, 16, 16, 24, 18])

    pdf.subtitulo("Por alumno")
    if informe["alumnos"]:
        pdf.tabla(["Alumno", "Curso", "P", "T", "A", "% asist.", "Faltas",
                   "Estado"],
                  [[a["nombre"], a["curso"], a["presentes"], a["tardanzas"],
                    a["ausentes"], f"{a['porcentaje_asistencia']} %",
                    f"{a['situacion']['faltas_texto']}/"
                    f"{a['situacion']['limite']}",
                    ESTADOS_LIMITE[a["situacion"]["estado"]]]
                   for a in informe["alumnos"]],
                  [42, 40, 9, 9, 9, 18, 16, 37])
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, "No hay alumnos para este filtro.")
    return bytes(pdf.output())
