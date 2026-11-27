"""
Paquete principal del Sistema de Asistencia de Alumnos.

Módulos:
    bd            Conexión a SQLite y creación del esquema.
    modelos       Clases que representan las entidades del sistema.
    validaciones  Validación y limpieza de los datos de entrada.
    seguridad     Hash y verificación de contraseñas.
    servicios     Reglas del sistema (alumnos, asistencia, informes...).
    interfaz      Aplicación web (rutas de FastAPI y plantillas).
    migracion     Importación de los datos del antiguo archivo JSON.
"""
