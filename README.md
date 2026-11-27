# Sistema de Asistencia de Alumnos

Sistema web para registrar la asistencia de alumnos por DNI.
Hecho con **Python + FastAPI**, **HTML + CSS + JavaScript** y los datos guardados en una base **SQLite**.

## Funciones

- **Dashboard** (pantalla de inicio): alumnos, presentes, tardanzas y ausentes de hoy,
  % de asistencia general, gráfico de los últimos 7 días con registros (con detalle al
  pasar el mouse y vista en tabla) y los alumnos con más ausencias y más tardanzas.
- **Login multiusuario con roles** (email y contraseña, guardada como hash):
  | Rol | Puede |
  |---|---|
  | **Administrador** | Todo lo del docente, más la pantalla **Usuarios**: crear cuentas de alumno y pasar cuentas de docente a administrador (y al revés). |
  | **Docente** | Dashboard, registrar asistencia, alta de alumnos, informes y hora límite. |
  | **Alumno** | Solo **Mi asistencia**: su propio informe. |

  La **primera cuenta** que se crea en una base vacía queda como administrador;
  las siguientes, como docentes. Siempre queda al menos un administrador.
  Sin iniciar sesión no se puede ver ni usar ninguna pantalla, y cada rol
  recibe "No tenés permiso" (403) en las pantallas que no le corresponden.
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
├── app.py                  # Punto de entrada: python app.py
├── migrar_json.py          # Pasa los datos del antiguo JSON a SQLite
├── gestionar_usuarios.py   # Lista cuentas y da el rol de administrador
├── main.py                 # Módulo de consola original (v2.1.0)
├── asistencia/
│   ├── bd.py               # Conexión a SQLite, esquema y transacciones
│   ├── modelos.py          # Clases de datos: Usuario, Alumno, RegistroAsistencia
│   ├── validaciones.py     # Validación de DNI, nombres, emails, fechas, horas
│   ├── seguridad.py        # Hash de contraseñas (scrypt)
│   ├── migracion.py        # Lectura del JSON viejo e importación
│   ├── servicios/          # Reglas del sistema
│   │   ├── usuarios.py     # Cuentas y login
│   │   ├── alumnos.py      # Alta, búsqueda y listado
│   │   ├── asistencias.py  # Registro, carga manual y cierre del día
│   │   ├── configuracion.py# Hora límite
│   │   └── informes.py     # Informe por alumno y dashboard
│   └── interfaz/           # Aplicación web (FastAPI)
│       ├── __init__.py     # crear_app(): rutas, sesión y errores
│       ├── comun.py        # Plantillas, mensajes, conexión y sesión
│       └── rutas_*.py      # Pantallas agrupadas por tema
├── templates/              # Páginas HTML
├── static/                 # CSS, JavaScript y fuentes
├── tests/                  # Pruebas con pytest (base en memoria)
├── datos/                  # Se crea sola: acá queda asistencia.db
├── requirements.txt
├── .flake8                 # Configuración de PEP 8
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

### Pasar los datos del JSON anterior

Las versiones anteriores guardaban todo en `datos/asistencia.json`. Para pasar
esos datos a la base SQLite (los docentes conservan su contraseña):
```
python migrar_json.py
```
El JSON no se modifica y queda como respaldo. Se puede ejecutar más de una
vez sin duplicar datos.

Las cuentas migradas quedan como **docentes**. Para elegir quién administra:
```
python gestionar_usuarios.py listar
python gestionar_usuarios.py hacer-admin email@escuela.edu.ar
```

> **Base de datos:** por defecto es `datos/asistencia.db`. Para usar otra,
> definí la variable de entorno `ASISTENCIA_BD` con la ruta del archivo.

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
flake8
```
Los tests usan bases SQLite en memoria: nunca tocan `datos/asistencia.db`.

## Validaciones

Todas se hacen **en el servidor** (`asistencia/validaciones.py` y `asistencia/servicios/`); el navegador solo ayuda.

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
- Varios usuarios pueden trabajar a la vez: SQLite en modo WAL, transacciones
  `BEGIN IMMEDIATE` y restricciones `UNIQUE` en la base (DNI, email, un registro
  por alumno y fecha), así dos pedidos simultáneos nunca duplican ni pisan datos.
- Si la base no responde o está dañada, se muestra una página de error clara.

## Tablas de la base

| Tabla | Contenido |
|---|---|
| `usuarios` | Cuentas: email (único), nombre, apellido, hash de la clave, rol (`administrador`, `docente` o `alumno`) y alumno vinculado |
| `alumnos` | DNI (único), nombre y apellido |
| `asistencias` | Alumno, fecha, estado, hora y si fue carga manual (un registro por alumno y fecha) |
| `dias_cerrados` | Fechas cerradas |
| `configuracion` | Opciones del sistema (hora límite) |
