"""
bd.py - Conexión a la base de datos SQLite y esquema de tablas.

Cada request de la aplicación web abre su propia conexión y la cierra al
terminar. Para que varios usuarios puedan trabajar a la vez:

- Se usa el modo WAL: las lecturas no bloquean a las escrituras.
- Las escrituras se hacen dentro de transaccion(), que usa
  BEGIN IMMEDIATE: si dos personas guardan al mismo tiempo, la segunda
  espera a que termine la primera (hasta TIEMPO_ESPERA segundos) en lugar
  de pisar sus cambios.
- Las restricciones UNIQUE de la base impiden duplicados aunque dos
  pedidos lleguen exactamente juntos.

El esquema se versiona con PRAGMA user_version: cada elemento de
MIGRACIONES lleva la base de una versión a la siguiente.
"""
import os
import sqlite3
from contextlib import contextmanager

CARPETA_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_POR_DEFECTO = os.path.join(CARPETA_BASE, "datos", "asistencia.db")
TIEMPO_ESPERA = 10   # segundos que se espera si otro usuario está guardando

# Cada migración es una lista de sentencias SQL. Nunca se modifica una
# migración ya publicada: los cambios nuevos van en una migración nueva.
MIGRACIONES = [
    # Versión 1: tablas equivalentes al antiguo archivo JSON.
    [
        """
        CREATE TABLE configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE usuarios (
            id         INTEGER PRIMARY KEY,
            email      TEXT NOT NULL UNIQUE,
            nombre     TEXT NOT NULL,
            apellido   TEXT NOT NULL,
            clave_hash TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE alumnos (
            id       INTEGER PRIMARY KEY,
            dni      TEXT NOT NULL UNIQUE,
            nombre   TEXT NOT NULL,
            apellido TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE asistencias (
            id        INTEGER PRIMARY KEY,
            alumno_id INTEGER NOT NULL REFERENCES alumnos(id),
            fecha     TEXT NOT NULL,
            estado    TEXT NOT NULL
                      CHECK (estado IN ('PRESENTE', 'TARDANZA', 'AUSENTE')),
            hora      TEXT,
            manual    INTEGER NOT NULL DEFAULT 0,
            UNIQUE (alumno_id, fecha)
        )
        """,
        "CREATE INDEX idx_asistencias_fecha ON asistencias (fecha)",
        """
        CREATE TABLE dias_cerrados (
            fecha TEXT PRIMARY KEY
        )
        """,
        "INSERT INTO configuracion (clave, valor) "
        "VALUES ('hora_limite', '08:15')",
    ],
    # Versión 2: roles de usuario. Las cuentas existentes quedan como
    # docentes; una cuenta de alumno se vincula con su alumno.
    [
        """
        ALTER TABLE usuarios ADD COLUMN rol TEXT NOT NULL DEFAULT 'docente'
            CHECK (rol IN ('administrador', 'docente', 'alumno'))
        """,
        "ALTER TABLE usuarios ADD COLUMN alumno_id INTEGER "
        "REFERENCES alumnos(id)",
        "CREATE UNIQUE INDEX idx_usuarios_alumno ON usuarios (alumno_id)",
    ],
    # Versión 3: docentes, materias, cursos y horarios. Los alumnos suman
    # email y curso (opcionales para los alumnos que ya existían).
    [
        """
        CREATE TABLE docentes (
            id       INTEGER PRIMARY KEY,
            dni      TEXT NOT NULL UNIQUE,
            nombre   TEXT NOT NULL,
            apellido TEXT NOT NULL,
            email    TEXT NOT NULL UNIQUE
        )
        """,
        """
        CREATE TABLE materias (
            id     INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL UNIQUE COLLATE NOCASE
        )
        """,
        """
        CREATE TABLE docente_materias (
            docente_id INTEGER NOT NULL
                       REFERENCES docentes(id) ON DELETE CASCADE,
            materia_id INTEGER NOT NULL REFERENCES materias(id),
            PRIMARY KEY (docente_id, materia_id)
        )
        """,
        """
        CREATE TABLE cursos (
            id         INTEGER PRIMARY KEY,
            nombre     TEXT NOT NULL,
            anio       INTEGER NOT NULL CHECK (anio BETWEEN 1 AND 7),
            division   TEXT NOT NULL,
            docente_id INTEGER NOT NULL REFERENCES docentes(id),
            UNIQUE (nombre, anio, division)
        )
        """,
        """
        CREATE TABLE horarios (
            id          INTEGER PRIMARY KEY,
            curso_id    INTEGER NOT NULL
                        REFERENCES cursos(id) ON DELETE CASCADE,
            dia         INTEGER NOT NULL CHECK (dia BETWEEN 0 AND 6),
            hora_inicio TEXT NOT NULL,
            hora_fin    TEXT NOT NULL,
            materia_id  INTEGER NOT NULL REFERENCES materias(id),
            CHECK (hora_inicio < hora_fin)
        )
        """,
        "CREATE INDEX idx_horarios_curso_dia ON horarios (curso_id, dia)",
        "ALTER TABLE alumnos ADD COLUMN email TEXT",
        "ALTER TABLE alumnos ADD COLUMN curso_id INTEGER "
        "REFERENCES cursos(id)",
        "CREATE UNIQUE INDEX idx_alumnos_email ON alumnos (email)",
    ],
]


def ruta_configurada():
    """Ruta de la base: la variable ASISTENCIA_BD o datos/asistencia.db."""
    return os.environ.get("ASISTENCIA_BD") or RUTA_POR_DEFECTO


def conectar(ruta=None):
    """
    Abre una conexión a la base y la deja lista para usar.

    La ruta puede ser un archivo, ":memory:" o una URI de SQLite
    (por ejemplo "file:prueba?mode=memory&cache=shared", que usan los
    tests para tener una base en memoria compartida).
    """
    ruta = ruta or ruta_configurada()
    es_uri = ruta.startswith("file:")
    if not es_uri and ruta != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)

    # isolation_level=None: las transacciones se manejan a mano con
    # transaccion(). check_same_thread=False: FastAPI puede abrir la
    # conexión en un hilo y usarla en otro (nunca en dos a la vez).
    conexion = sqlite3.connect(ruta, timeout=TIEMPO_ESPERA, uri=es_uri,
                               isolation_level=None,
                               check_same_thread=False)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.execute(f"PRAGMA busy_timeout = {TIEMPO_ESPERA * 1000}")
    if not es_uri and ruta != ":memory:":
        conexion.execute("PRAGMA journal_mode = WAL")
    crear_esquema(conexion)
    return conexion


def crear_esquema(conexion):
    """Aplica las migraciones que falten. Si la base está al día, no hace
    nada."""
    version = conexion.execute("PRAGMA user_version").fetchone()[0]
    if version >= len(MIGRACIONES):
        return
    with transaccion(conexion):
        # Se vuelve a leer la versión ya con la base bloqueada, por si otro
        # proceso aplicó las migraciones mientras tanto.
        version = conexion.execute("PRAGMA user_version").fetchone()[0]
        for numero in range(version, len(MIGRACIONES)):
            for sentencia in MIGRACIONES[numero]:
                conexion.execute(sentencia)
        conexion.execute(f"PRAGMA user_version = {len(MIGRACIONES)}")


@contextmanager
def transaccion(conexion):
    """
    Agrupa varias operaciones de escritura: se guardan todas o ninguna.

    Uso:
        with transaccion(conexion):
            conexion.execute(...)
            conexion.execute(...)

    Si ocurre cualquier error dentro del bloque, se deshacen los cambios.
    """
    conexion.execute("BEGIN IMMEDIATE")
    try:
        yield conexion
    except BaseException:
        conexion.execute("ROLLBACK")
        raise
    conexion.execute("COMMIT")
