# Sistema de Asistencia de Alumnos

[![Tests y PEP 8](https://github.com/Daynara22/asistencia-scm-practica1/actions/workflows/tests.yml/badge.svg)](https://github.com/Daynara22/asistencia-scm-practica1/actions/workflows/tests.yml)

Sistema web para registrar la asistencia de alumnos por DNI.
Hecho con **Python + FastAPI**, **HTML + CSS + JavaScript** y los datos guardados en una base **SQLite**.

> El informe del trabajo práctico (objetivo, funcionalidades agregadas, tests,
> pipeline y herramientas) está en [INFORME.md](INFORME.md).

## Funciones

- **Interfaz moderna y responsive** con **menú lateral** (se abre y cierra con
  el botón de hamburguesa; en celulares se oculta solo), **modo claro / oscuro**
  que se recuerda, íconos y tarjetas. Cada rol ve solo sus opciones.
- **Gráficos** (sección *Gráficos*): dona con presentes / tardanzas /
  ausentes, barras comparando a los alumnos de un curso y línea con la
  evolución de la asistencia, con filtros y adaptados a los dos modos.

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
- **ABM (alta, baja y modificación)** de:
  | Entidad | Datos | Validaciones |
  |---|---|---|
  | **Alumnos** | DNI, nombre, apellido, email, curso | DNI y email únicos; email y curso obligatorios al dar de alta (opcionales al editar alumnos anteriores). La baja borra también su asistencia y su cuenta. |
  | **Docentes** | DNI, nombre, apellido, email, materias | DNI y email únicos; al menos una materia. No se da de baja si está a cargo de un curso. Si hay una cuenta con su email, aparece "con cuenta". |
  | **Cursos** | Nombre, año (1 a 7), división, docente a cargo | Sin cursos repetidos (nombre + año + división). No se da de baja si tiene alumnos; sus horarios se borran con él. |
  | **Horarios** | Curso, día, hora de inicio y fin, materia | Fin posterior al inicio; **sin superposición** con otro bloque del mismo curso y día (pueden tocarse: 08:00–09:00 y 09:00–10:00). |

  Docentes y administradores dan de alta y editan alumnos; solo el
  administrador da de baja alumnos y modifica docentes, cursos y horarios
  (el docente ve esos listados sin poder cambiarlos). Las materias se crean
  solas al escribirlas en un docente o un horario.
- **Límite de faltas** (pantalla *Configuración*):
  - Límite **general** (por defecto 10 faltas) y, opcionalmente, un límite
    **propio de cada curso** que reemplaza al general.
  - Cada ausencia es una falta. Se configura cuántas tardanzas equivalen a
    una falta: no suman (por defecto), 4, 2 o 1.
  - **Alertas**: "cerca del límite" desde el **75 %** del límite y "límite
    superado" cuando lo pasa. Se ven en el informe del alumno (también en
    *Mi asistencia*), en el listado de alumnos (faltas / límite con color) y
    en el dashboard (*Alertas de faltas*).
  - Docentes ven la configuración; solo el administrador la cambia.
- **Registro por DNI**: se ingresa el DNI y el sistema guarda la hora y calcula el estado solo.
  - Hasta la hora límite (inclusive) → **PRESENTE**
  - Después de la hora límite → **TARDANZA**
- **Hora límite configurable** desde la pantalla principal (por defecto 08:15).
- **Cerrar el día**: marca **AUSENTE** a quienes no se registraron y bloquea el día.
- **Carga manual** de una tardanza (con hora de llegada) o una ausencia de otra fecha.
- **Panel de informes** (menú *Informes*):
  - **Informe total**: resumen general y **por curso** (presentes, tardanzas,
    ausentes, % de asistencia y alumnos con alerta de faltas), una fila por
    alumno y un **gráfico de barras** apiladas por curso. Filtros por
    **fechas** (desde / hasta) y por **curso**.
  - **Informe por alumno**: cantidades, porcentajes, estado respecto del
    límite y detalle por fecha, con filtro por fechas.
  - **Exportación a CSV y PDF** de los dos informes (y de *Mi asistencia*
    para el alumno), respetando los filtros. El CSV usa `;` y coma decimal
    para abrirse bien en Excel en español.
  - El porcentaje de asistencia cuenta presentes + tardanzas. Las faltas y el
    límite siempre cuentan todo el ciclo, aunque se filtre por fechas.

## Estructura

```
asistencia-scm-practica1/
├── app.py                  # Punto de entrada: python app.py
├── migrar_json.py          # Pasa los datos del antiguo JSON a SQLite
├── gestionar_usuarios.py   # Lista cuentas y da el rol de administrador
├── main.py                 # Módulo de consola original (v2.1.0)
├── asistencia/
│   ├── bd.py               # Conexión a SQLite, esquema y transacciones
│   ├── modelos.py          # Clases de datos: Usuario, Alumno, Docente, Curso, Horario...
│   ├── validaciones.py     # Validación de DNI, nombres, emails, fechas, horas
│   ├── seguridad.py        # Hash de contraseñas (scrypt)
│   ├── migracion.py        # Lectura del JSON viejo e importación
│   ├── exportar.py         # Informes a CSV y PDF (fpdf2)
│   ├── servicios/          # Reglas del sistema
│   │   ├── usuarios.py     # Cuentas y login
│   │   ├── alumnos.py      # ABM de alumnos
│   │   ├── docentes.py     # ABM de docentes
│   │   ├── materias.py     # Materias (se crean solas)
│   │   ├── cursos.py       # ABM de cursos
│   │   ├── horarios.py     # ABM de horarios y superposición
│   │   ├── limites.py      # Límite de faltas y alertas
│   │   ├── graficos.py     # Datos y geometría de los gráficos SVG
│   │   ├── asistencias.py  # Registro, carga manual y cierre del día
│   │   ├── configuracion.py# Hora límite
│   │   └── informes.py     # Informe por alumno, total por curso y dashboard
│   └── interfaz/           # Aplicación web (FastAPI)
│       ├── __init__.py     # crear_app(): rutas, sesión y errores
│       ├── comun.py        # Plantillas, mensajes, conexión y sesión
│       ├── iconos.py       # Íconos SVG del menú y los botones
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
pytest            # 482 tests
pytest --cov      # con reporte de cobertura (mínimo 90 %, hoy 100 %)
flake8            # verificación de PEP 8
```
Los tests usan bases SQLite en memoria: nunca tocan `datos/asistencia.db`.

## Integración continua

El workflow [`.github/workflows/tests.yml`](.github/workflows/tests.yml) corre
en cada push y en cada pull request, con Python 3.10 y 3.13:

1. instala las dependencias de `requirements.txt`;
2. verifica PEP 8 con **flake8**;
3. ejecuta los tests con **pytest** y cobertura.

Si flake8 encuentra un aviso, si falla un test o si la cobertura baja del 90 %,
el pipeline queda en rojo (badge de arriba). El reporte de cobertura se
descarga desde la ejecución, en la pestaña **Actions** → *Artifacts*.

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
| `alumnos` | DNI (único), nombre, apellido, email (único) y curso |
| `docentes` | DNI y email (únicos), nombre y apellido |
| `materias` | Nombre (único, sin distinguir mayúsculas) |
| `docente_materias` | Qué materias dicta cada docente |
| `cursos` | Nombre, año, división, docente a cargo y límite de faltas propio (opcional) |
| `horarios` | Curso, día (0 = lunes), hora de inicio y fin, materia |
| `asistencias` | Alumno, fecha, estado, hora y si fue carga manual (un registro por alumno y fecha) |
| `dias_cerrados` | Fechas cerradas |
| `configuracion` | Opciones del sistema: hora límite, límite general de faltas y valor de la tardanza |
