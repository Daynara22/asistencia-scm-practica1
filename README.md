# Sistema de Asistencia de Alumnos

Sistema web para registrar la asistencia de alumnos por DNI.
Hecho con **Python + FastAPI**, **HTML + CSS + JavaScript** y los datos guardados en **JSON**.

## Funciones

- **Dashboard** (pantalla de inicio): alumnos, presentes, tardanzas y ausentes de hoy,
  % de asistencia general, gráfico de los últimos 7 días con registros (con detalle al
  pasar el mouse y vista en tabla) y los alumnos con más ausencias y más tardanzas.
- **Login de docentes** con email y contraseña. Cada docente crea su cuenta desde
  «Crear cuenta de docente». Al entrar, la barra superior muestra
  **"Bienvenido docente"** y el nombre del docente que inició sesión.
  Sin iniciar sesión no se puede ver ni usar ninguna pantalla del sistema.
- **Alta de alumnos** con DNI, nombre y apellido (sin DNI repetidos).
- **Registro por DNI**: se ingresa el DNI y el sistema guarda la hora y calcula el estado solo.
  - Hasta la hora límite (inclusive) → **PRESENTE**
  - Después de la hora límite → **TARDANZA**
- **Hora límite configurable** desde la pantalla principal (por defecto 08:15).
- **Cerrar el día**: marca **AUSENTE** a quienes no se registraron y bloquea el día.
- **Carga manual** de una tardanza (con hora de llegada) o una ausencia de otra fecha.
- **Informe por alumno**: presentes, tardanzas, ausentes, porcentajes y detalle por fecha.
  El porcentaje de asistencia cuenta presentes + tardanzas.

## Estructura

```
asistencia-scm-practica1/
├── app.py              # Rutas de FastAPI (pantallas y formularios)
├── logica.py           # Reglas del sistema y validaciones
├── datos.py            # Lectura y guardado del archivo JSON
├── templates/          # Páginas HTML
│   ├── base.html       # Estructura común (menú, saludo y mensajes)
│   ├── login.html      # Ingreso de docentes
│   ├── registro_docente.html  # Crear cuenta de docente
│   ├── dashboard.html  # Dashboard (pantalla de inicio)
│   ├── index.html      # Registrar asistencia
│   ├── alumnos.html    # Alta y listado de alumnos
│   ├── informe.html    # Informe por alumno
│   └── error.html      # Página de error amigable
├── static/
│   ├── estilos.css     # Diseño
│   ├── app.js          # Reloj, confirmaciones, buscador, contraseña, gráfico
│   └── fuentes/        # Fuente Plus Jakarta Sans (licencia OFL)
├── tests/              # Pruebas con pytest
├── datos/              # Se crea sola: acá queda asistencia.json
├── requirements.txt
└── pytest.ini
```

## Instalación y ejecución

Necesitás **Python 3.10 o superior**. Abrí una terminal en la carpeta `asistencia-scm-practica1`.

**Windows**
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

**Linux / macOS**
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Después abrí en el navegador: **http://127.0.0.1:5000**

La primera vez, entrá a **Crear cuenta de docente** para registrarte.

> **Clave de sesión:** el login usa una cookie firmada. Para que las sesiones
> sigan abiertas después de reiniciar el servidor, definí la variable de entorno
> `SECRET_KEY` con un texto largo y secreto antes de ejecutar `python app.py`
> (Windows: `set SECRET_KEY=...` · Linux/macOS: `export SECRET_KEY=...`).
> Si no se define, se genera una al azar en cada arranque.

Para detener el servidor: `Ctrl + C` en la terminal.

También se puede iniciar con recarga automática (útil mientras se programa):
```
uvicorn app:app --reload --port 5000
```

## Ejecutar los tests

Con el entorno activado:
```
pytest
```

## Validaciones

Todas se hacen **en el servidor** (`logica.py`); el navegador solo ayuda.

- Email del docente: formato válido (`nombre@dominio.ext`), sin repetir. Se guarda en minúsculas.
- Contraseña del docente: **mínimo 8 caracteres**, con al menos **una letra**, **un número**
  y **un carácter especial** (por ejemplo `! @ # $ % & * ?`), sin espacios.
  Se pide dos veces y se guarda **como hash**, nunca tal cual.
- Si el email o la contraseña son incorrectos, el mensaje no dice cuál de los dos falló.
- DNI: solo números, 7 u 8 dígitos (se aceptan puntos, ej. 45.123.456, y se quitan).
- Nombre y apellido: obligatorios, solo letras (con tildes y ñ), espacios, guiones o apóstrofos.
- No se repiten DNI. Un solo registro por alumno y por día.
- Fechas `AAAA-MM-DD` que existan y no sean futuras; horas `HH:MM` válidas.
  Las horas se comparan como horas (objetos `time`), no como texto.
- No se puede registrar en un día cerrado ni cerrar el mismo día dos veces.
- Si `datos/asistencia.json` está dañado, el sistema no se cierra: guarda una copia
  (`asistencia.danado-FECHA.json`), avisa en pantalla y sigue con datos vacíos.
- El guardado es seguro: se escribe un archivo temporal y después se reemplaza.

## Formato del JSON

```json
{
  "config": {"hora_limite": "08:15"},
  "alumnos": {
    "45123456": {"nombre": "Juan", "apellido": "Pérez"}
  },
  "asistencias": {
    "2026-11-06": {
      "45123456": {"estado": "PRESENTE", "hora": "08:02", "manual": false}
    }
  },
  "dias_cerrados": ["2026-11-06"],
  "docentes": {
    "maria.gonzalez@escuela.edu.ar": {"nombre": "María", "apellido": "González", "clave": "<hash>"}
  }
}
```
