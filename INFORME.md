# Informe final – Sistema de Control de Asistencia

[![Tests y PEP 8](https://github.com/Daynara22/asistencia-scm-practica1/actions/workflows/tests.yml/badge.svg)](https://github.com/Daynara22/asistencia-scm-practica1/actions/workflows/tests.yml)

## 1. Objetivo del sistema

El sistema registra la asistencia diaria de los alumnos de una institución
educativa a partir de su DNI. Calcula solo si el alumno llegó a horario
(PRESENTE) o tarde (TARDANZA) según una hora límite, y al cerrar el día marca
AUSENTE a quien no se registró.

En este trabajo práctico amplié la versión inicial, que era de un solo usuario
y guardaba todo en un archivo JSON, para que:

- la usen **varias personas a la vez**, con **roles y permisos distintos**;
- administre **alumnos, docentes, cursos y horarios**;
- controle un **límite de faltas** y avise a tiempo;
- ofrezca un **panel de informes** con filtros, gráficos y exportación;
- tenga **tests automáticos**, cumpla **PEP 8** y se verifique en un
  **pipeline de integración continua**.

## 2. Funcionalidades agregadas

### 2.1 Multiusuario, login y roles

- Inicio de sesión con email y contraseña. Las contraseñas **nunca se guardan
  en texto plano**: guardo un hash **scrypt** con una sal aleatoria distinta
  para cada una. Las contraseñas deben tener al menos 8 caracteres, con una
  letra, un número y un carácter especial.
- Tres roles con permisos distintos, controlados **en el servidor** en cada
  ruta (si alguien entra a una pantalla que no le corresponde recibe
  "No tenés permiso", código 403):

  | Rol | Permisos |
  |---|---|
  | **Administrador** | Todo, más la gestión de cuentas (pantalla *Usuarios*), el ABM de docentes, cursos y horarios, la baja de alumnos y la configuración del límite de faltas. |
  | **Docente** | Registrar asistencia, alta y edición de alumnos, informes y dashboard. Ve docentes, cursos, horarios y límites, pero no los modifica. |
  | **Alumno** | Solo *Mi asistencia*: su propio informe, con alertas y descarga. |

- La primera cuenta que se crea en una base vacía queda como administradora,
  y siempre tiene que quedar al menos un administrador. El script
  `gestionar_usuarios.py` permite listar cuentas y nombrar administradores
  desde la terminal.

**Acceso concurrente.** La versión original leía y reescribía un archivo JSON
completo en cada operación: si dos usuarios guardaban a la vez, el segundo
pisaba los cambios del primero. Migré los datos a **SQLite** con:

- una conexión por cada pedido, que se cierra al terminar;
- modo **WAL**, para que las lecturas no bloqueen a las escrituras;
- transacciones **`BEGIN IMMEDIATE`**: si dos usuarios guardan a la vez, el
  segundo espera a que termine el primero en lugar de pisarlo;
- restricciones **`UNIQUE`** en la base (DNI, email, un registro por alumno y
  fecha) que impiden duplicados aunque dos pedidos lleguen exactamente juntos;
- un esquema **versionado** (`PRAGMA user_version`, hoy en la versión 4) que
  actualiza solas las bases existentes sin perder datos.

El script `migrar_json.py` pasa los datos del JSON anterior a SQLite (los
docentes conservan su contraseña) y se puede ejecutar más de una vez sin
duplicar nada.

### 2.2 ABM de entidades

| Entidad | Datos | Validaciones principales |
|---|---|---|
| Alumnos | Nombre, apellido, DNI, email, curso | DNI y email únicos; email válido; curso existente. La baja borra también su asistencia y su cuenta. |
| Docentes | Nombre, apellido, DNI, email, materias | DNI y email únicos; al menos una materia. No se puede dar de baja a un docente a cargo de un curso. |
| Cursos | Nombre, año (1 a 7), división, docente a cargo | Sin cursos repetidos (nombre + año + división). No se puede dar de baja un curso con alumnos. |
| Horarios | Curso, día, hora de inicio y fin, materia | La hora de fin debe ser posterior a la de inicio y **no puede superponerse** con otro bloque del mismo curso y día. Si choca, el mensaje dice con qué bloque. |

Cada pantalla tiene alta, edición, baja con confirmación y listado (alumnos y
horarios también con filtro por curso). Las materias se crean solas al
escribirlas en un docente o en un horario.

### 2.3 Límite de faltas

- Límite **general** configurable (por defecto 10 faltas) y, opcionalmente,
  un límite **propio de cada curso**.
- Se registran tres estados: **presente**, **tardanza** y **ausente**. Cada
  ausencia es una falta y se configura **cuántas tardanzas equivalen a una
  falta**: no suman (por defecto), 4, 2 o 1. Calculo las faltas con
  fracciones exactas para evitar errores de redondeo.
- **Alertas:** "cerca del límite" desde el **75 %** del límite y "límite
  superado" al pasarlo. Se muestran en el informe del alumno, en *Mi
  asistencia*, en el listado de alumnos y en el dashboard.

### 2.4 Panel de informes

- **Informe por alumno:** presentes, tardanzas, ausentes, porcentaje de
  asistencia, estado respecto del límite y detalle por fecha, con filtro por
  fechas.
- **Informe total:** resumen general y por curso (cantidades, % de asistencia
  y alumnos con alerta) y una tabla por alumno con **clases asistidas,
  tardanzas, inasistencias, porcentaje de asistencia y estado respecto del
  límite**, con filtros por **curso, alumno y rango de fechas**.
- **Exportación a CSV y PDF** de todos los informes, respetando los filtros. El
  CSV usa `;` y coma decimal para abrirse bien en Excel en español; el PDF se
  genera con `fpdf2`, con tablas, gráfico y alertas.

### 2.5 Rediseño de la interfaz

- **Diseño moderno y responsive**: paleta coherente, tipografía Plus Jakarta
  Sans (incluida en el proyecto), espaciados consistentes, íconos SVG y
  tarjetas. Se adapta a computadora, tablet y celular.
- **Modo claro / modo oscuro** con un botón en la barra superior (también en
  el login). Todos los colores están definidos con **variables CSS** para los
  dos modos, así fondos, textos, tablas, formularios y gráficos cambian juntos.
  La preferencia se guarda en el navegador y, si no hay ninguna, se usa la del
  sistema operativo. El tema se aplica antes de dibujar la página, sin
  parpadeos.
- **Menú lateral desplegable** que se abre y cierra con el botón de
  hamburguesa (en computadora recuerda si quedó cerrado). En celulares se
  oculta solo y se abre encima del contenido. Resalta la pantalla actual y
  muestra solo las opciones del rol: Inicio, Tomar asistencia, Alumnos,
  Docentes, Cursos, Horarios, Usuarios (solo administrador), Informes,
  Gráficos, Configuración y Cerrar sesión. El alumno ve *Mi asistencia* y
  *Gráficos*.
- **Dashboard con tarjetas resumen**: total de alumnos, porcentaje de
  asistencia general y cantidad de alumnos cerca o por encima del límite de
  faltas, además de los números del día.
- **Sección de gráficos** (dibujados como SVG, sin librerías externas):
  - **dona** con la proporción de asistencias, tardanzas e inasistencias de un
    alumno (o de un curso);
  - **barras** comparando el porcentaje de asistencia de los alumnos de un
    curso;
  - **línea** con la evolución de la asistencia en el tiempo (por día, o por
    semana cuando hay muchos días).

  Todos tienen filtros, globos con el detalle al pasar el mouse o llegar con
  el teclado y una tabla con los datos. Los colores (presente azul, tardanza
  ámbar, ausente rojo) los validé con un script para que se distingan también
  con daltonismo, en los dos modos. El alumno solo ve sus propios gráficos.

## 3. Estructura del proyecto

Separé el código en módulos con responsabilidades claras: base de datos,
modelos, reglas (servicios) e interfaz web.

```
asistencia-scm-practica1/
├── app.py                  # Punto de entrada: python app.py
├── migrar_json.py          # Migración del JSON anterior a SQLite
├── gestionar_usuarios.py   # Listar cuentas y nombrar administradores
├── main.py                 # Módulo de consola original (v2.1.0)
├── asistencia/
│   ├── bd.py               # Base de datos: conexión, esquema y transacciones
│   ├── modelos.py          # Modelos: Usuario, Alumno, Docente, Curso, Horario...
│   ├── validaciones.py     # Validación de los datos de entrada
│   ├── seguridad.py        # Hash de contraseñas (scrypt)
│   ├── migracion.py        # Lectura e importación del JSON anterior
│   ├── exportar.py         # Exportación de informes a CSV y PDF
│   ├── servicios/          # Lógica: usuarios, alumnos, docentes, materias,
│   │                       # cursos, horarios, asistencias, límites,
│   │                       # informes y gráficos (datos y geometría SVG)
│   └── interfaz/           # Interfaz web: FastAPI, sesión, permisos, rutas
│                           # e íconos
├── templates/              # Páginas HTML (Jinja2)
├── static/                 # CSS, JavaScript y fuente
├── tests/                  # Tests con pytest
├── .github/workflows/      # Pipelines de GitHub Actions
├── requirements.txt        # Dependencias
├── .flake8                 # Configuración de PEP 8
├── .coveragerc             # Configuración de la cobertura
└── pytest.ini
```

Las capas solo se usan "hacia abajo": la interfaz llama a los servicios, los
servicios usan la base y los modelos, y ningún servicio sabe nada de la web.
Por eso los servicios se pueden probar sin levantar el servidor.

## 4. Instalación y uso

Se necesita **Python 3.10 o superior**.

```
git clone https://github.com/Daynara22/asistencia-scm-practica1.git
cd asistencia-scm-practica1
python -m venv venv
venv\Scripts\activate            # Linux / macOS: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Después se abre **http://127.0.0.1:5000** en el navegador.

1. La primera vez se crea una cuenta en *Crear cuenta de docente*: como es la
   primera, queda como administradora.
2. Orden sugerido de carga: **Docentes → Cursos → Horarios → Alumnos**.
3. Desde *Registrar asistencia* se ingresa el DNI de cada alumno al llegar.
   Al terminar el día, *Cerrar el día* marca los ausentes.
4. Desde *Usuarios* el administrador crea cuentas de alumno, para que cada
   alumno vea su propia asistencia.
5. *Configuración* define el límite de faltas y la equivalencia de las
   tardanzas; *Informes* muestra y exporta los resúmenes y *Gráficos* los
   muestra visualmente.
6. El botón de la luna / el sol (arriba a la derecha) cambia entre modo claro
   y oscuro; el botón de hamburguesa abre y cierra el menú.

Si había datos de la versión anterior: `python migrar_json.py` y después
`python gestionar_usuarios.py hacer-admin email@ejemplo.com`.

Variables de entorno opcionales: `ASISTENCIA_BD` (ruta de la base, por defecto
`datos/asistencia.db`) y `SECRET_KEY` (clave de la cookie de sesión, para que
las sesiones sigan abiertas al reiniciar el servidor).

## 5. Tests

Escribí los tests con **pytest**, separados por módulo. Todos usan bases
SQLite **en memoria** o temporales (nunca tocan los datos reales) y corren sin
interfaz gráfica, así que se pueden ejecutar en el pipeline.

```
pytest                 # todos los tests
pytest --cov           # con reporte de cobertura
flake8                 # verificación de PEP 8
```

| Módulo | Archivo(s) | Tests |
|---|---|---|
| Usuarios, login y roles | `test_usuarios.py`, `test_roles.py` | 62 |
| Alumnos | `test_alumnos.py` | 24 |
| Docentes | `test_docentes.py` | 16 |
| Cursos | `test_cursos.py` | 14 |
| Horarios | `test_horarios.py` | 18 |
| Asistencia | `test_asistencias.py` | 21 |
| Límite de faltas y equivalencia de tardanzas | `test_limites.py` | 50 |
| Informes y exportación | `test_informes.py`, `test_informes_web.py`, `test_exportar.py` | 54 |
| Gráficos (datos, geometría y pantalla) | `test_graficos.py` | 20 |
| Interfaz: menú por rol, modo oscuro, dashboard y filtros | `test_interfaz.py` | 25 |
| Pantallas y ABM web | `test_web.py`, `test_abm_web.py` | 83 |
| Validaciones, base de datos, migración, modelos y `main.py` | `test_validaciones.py`, `test_bd.py`, `test_migracion.py`, `test_modelos.py`, `test_main.py` | 95 |
| **Total** | | **482** |

Resultado al cerrar el trabajo:

```
482 passed in 14.80s
Required test coverage of 90.0% reached. Total coverage: 100.00%
flake8: 0 avisos
```

Algunos casos que verifican los tests:

- contraseñas guardadas solo como hash y login que no revela qué emails existen;
- cada rol entra solo a sus pantallas y formularios;
- diez usuarios registrando asistencia a la vez sin perder registros, y un
  segundo usuario que espera mientras otro guarda;
- cinco formas distintas de superposición de horarios;
- el paso de "normal" a "cerca" justo en el 75 % del límite y a "superado"
  apenas lo pasa;
- contenido de los CSV leído como lo haría Excel, y PDF válidos de varias
  páginas;
- migración de una base de una versión anterior sin pérdida de datos.

Durante esta etapa los tests me permitieron encontrar y corregir un error real:
cuando el archivo de la base estaba dañado, la conexión quedaba abierta.

## 6. Pipeline de integración continua

El workflow [`.github/workflows/tests.yml`](.github/workflows/tests.yml) se
ejecuta en **cada push** y en **cada pull request**, con **Python 3.10 y
3.13** en paralelo. Sus pasos son:

1. Descargar el código del repositorio.
2. Instalar Python (con caché de dependencias).
3. Instalar las dependencias de `requirements.txt`.
4. **Verificar PEP 8 con flake8**: cualquier aviso hace fallar el pipeline.
5. **Ejecutar todos los tests con pytest y cobertura**: falla si algún test
   falla o si la cobertura baja del 90 % (definido en `.coveragerc`).
6. Guardar el reporte de cobertura (XML y HTML) como artefacto descargable.

El estado se ve en el badge al principio de este informe y del README: verde
si todo pasó, rojo si algo falló. El repositorio mantiene además los
workflows anteriores: `tareas-nocturnas.yml` (respaldo simulado y tests de
lunes a viernes a las 00:30, hora de Argentina) y `verify-release.yml`
(verificación al publicar una versión con tag).

**Cómo verificar en GitHub que el pipeline corrió bien:**

1. Entrar al repositorio y abrir la pestaña **Actions**.
2. Elegir el workflow **"Tests y PEP 8"** en la columna izquierda.
3. La ejecución más reciente tiene que tener una **tilde verde**. Al abrirla se
   ven los dos trabajos (Python 3.10 y 3.13) y, en cada uno, la salida de
   flake8 y de pytest con la cantidad de tests y la cobertura.
4. Abajo de todo, en **Artifacts**, se descarga el reporte de cobertura;
   dentro está `htmlcov/index.html`.
5. En el pull request, la sección de verificaciones ("checks") también
   muestra el resultado antes de hacer el merge.

## 7. Buenas prácticas (PEP 8)

- Todo el código cumple PEP 8 y lo verifica **flake8** (líneas de 79
  caracteres como máximo, configurado en `.flake8`), tanto localmente como en
  el pipeline.
- Nombres en `snake_case`, imports ordenados (biblioteca estándar, terceros y
  propios) y **docstrings** en todos los módulos, clases y funciones.
- Código y comentarios en español.
- Consultas SQL siempre con parámetros (`?`), nunca armadas pegando texto
  ingresado por el usuario.
- Commits pequeños y descriptivos por funcionalidad, con prefijos
  convencionales (`feat:`, `fix:`, `test:`, `docs:`, `ci:`...), en una rama
  aparte (`feature/tp-ampliacion`) que se integra a `main` por pull request.

## 8. Herramientas utilizadas

| Herramienta | Uso |
|---|---|
| Python 3.10 / 3.13 | Lenguaje del sistema. |
| FastAPI + Uvicorn | Aplicación web y servidor. |
| Jinja2, HTML, CSS y JavaScript | Pantallas (sin frameworks de frontend). |
| SQLite (`sqlite3`) | Base de datos con acceso concurrente. |
| fpdf2 | Exportación de informes a PDF. |
| pytest, pytest-cov, httpx | Tests unitarios y de la interfaz web, y cobertura. |
| flake8 | Verificación de PEP 8. |
| Git, GitHub y GitHub Actions | Control de versiones, pull requests e integración continua. |
| Visual Studio Code | Editor. |
| **Claude Code (Anthropic)** | Asistente de programación con IA. |

**Uso de la IA.** Trabajé con Claude Code como asistente durante todo el
trabajo práctico. Generó gran parte del código, de los tests y de la
documentación a partir de mis indicaciones. Avancé por etapas: en cada una
revisé los cambios y tomé las decisiones de diseño. Por ejemplo:

- cómo se crea el primer administrador;
- que la asistencia siga siendo diaria;
- que las tardanzas no sumen faltas por defecto;
- que el límite de faltas cuente todo el ciclo, aunque se filtre por fechas;
- usar `fpdf2` para los PDF.

La IA también ayudó a detectar problemas, como la pérdida de datos con varios
usuarios en el JSON, una conexión que quedaba abierta y diferencias de
versión de FastAPI. Cada cambio se verificó con los tests y con flake8 antes
de cada commit.

## 9. Posibles mejoras futuras

- **Asistencia por clase**: registrar la asistencia por materia y bloque
  horario (hoy es diaria), usando los horarios ya cargados.
- **Recuperación de contraseña** por email y cambio de contraseña desde el
  perfil.
- **Notificaciones** por email al alumno (o a su familia) cuando se acerca al
  límite de faltas.
- **Justificación de inasistencias** con certificado adjunto, para que no
  cuenten para el límite.
- Superposición de horarios **por docente**, para que un docente no tenga dos
  clases a la misma hora en cursos distintos.
- **Bajas lógicas** (archivar alumnos en lugar de borrarlos) para conservar el
  historial de años anteriores.
- Migrar a **PostgreSQL** si la cantidad de usuarios simultáneos crece mucho.
- Registro de **auditoría** (quién cambió qué y cuándo).
- Despliegue automático (CD) a un servidor cuando el pipeline pasa en `main`.
- Instalar la aplicación como PWA para usarla desde el celular sin navegador.
