"""
app.py - Punto de entrada del sistema web.

Uso:
    python app.py

y abrir http://127.0.0.1:5000 en el navegador.

La base de datos se guarda en datos/asistencia.db (o en la ruta de la
variable de entorno ASISTENCIA_BD).
"""
from asistencia.interfaz import crear_app

app = crear_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5000)
