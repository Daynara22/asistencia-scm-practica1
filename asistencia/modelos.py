"""
modelos.py - Clases que representan las entidades del sistema.

Son clases de datos simples (dataclasses): no acceden a la base ni
validan nada. Los servicios las crean a partir de las filas de SQLite
con el método desde_fila().
"""
from dataclasses import dataclass, field
from typing import List, Optional

PRESENTE = "PRESENTE"
TARDANZA = "TARDANZA"
AUSENTE = "AUSENTE"
ESTADOS = (PRESENTE, TARDANZA, AUSENTE)

# Roles de usuario y lo que puede hacer cada uno:
# - administrador: todo, incluida la gestión de cuentas de usuario.
# - docente: registrar asistencia, alumnos, informes y dashboard.
# - alumno: solo ver su propio informe de asistencia.
ADMINISTRADOR = "administrador"
DOCENTE = "docente"
ALUMNO = "alumno"
ROLES = (ADMINISTRADOR, DOCENTE, ALUMNO)

# Días de la semana, en el orden de date.weekday() (0 = lunes).
DIAS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado",
        "Domingo")


def _campos_de_fila(clase, fila):
    """Toma de la fila solo las columnas que existen en la clase."""
    claves = fila.keys()
    return {campo: fila[campo] for campo in clase.__dataclass_fields__
            if campo in claves}


@dataclass
class Usuario:
    """Cuenta para entrar al sistema, con su rol."""

    id: int
    email: str
    nombre: str
    apellido: str
    clave_hash: str = ""
    rol: str = DOCENTE
    alumno_id: Optional[int] = None     # solo en las cuentas de alumno

    @classmethod
    def desde_fila(cls, fila):
        """Crea el usuario a partir de una fila de la tabla usuarios."""
        return cls(**_campos_de_fila(cls, fila))

    @property
    def nombre_completo(self):
        """Nombre y apellido juntos, para mostrar en pantalla."""
        return f"{self.nombre} {self.apellido}"

    @property
    def es_administrador(self):
        """True si la cuenta es de un administrador."""
        return self.rol == ADMINISTRADOR

    @property
    def es_alumno(self):
        """True si la cuenta es de un alumno."""
        return self.rol == ALUMNO


@dataclass
class Alumno:
    """Alumno identificado por su DNI."""

    id: int
    dni: str
    nombre: str
    apellido: str
    # Opcionales: los alumnos anteriores a la versión 3 no los tienen.
    email: Optional[str] = None
    curso_id: Optional[int] = None

    @classmethod
    def desde_fila(cls, fila):
        """Crea el alumno a partir de una fila de la tabla alumnos."""
        return cls(**_campos_de_fila(cls, fila))

    @property
    def nombre_completo(self):
        """Nombre y apellido juntos, para mostrar en pantalla."""
        return f"{self.nombre} {self.apellido}"


@dataclass
class RegistroAsistencia:
    """Asistencia de un alumno en una fecha."""

    id: int
    alumno_id: int
    fecha: str              # AAAA-MM-DD
    estado: str             # PRESENTE, TARDANZA o AUSENTE
    hora: Optional[str]     # HH:MM, o None en las ausencias
    manual: bool

    @classmethod
    def desde_fila(cls, fila):
        """Crea el registro a partir de una fila de la tabla
        asistencias."""
        campos = _campos_de_fila(cls, fila)
        campos["manual"] = bool(campos["manual"])
        return cls(**campos)


@dataclass
class Docente:
    """Docente de la institución, con las materias que dicta."""

    id: int
    dni: str
    nombre: str
    apellido: str
    email: str
    materias: List[str] = field(default_factory=list)

    @classmethod
    def desde_fila(cls, fila, materias=()):
        """Crea el docente a partir de una fila de la tabla docentes."""
        return cls(**_campos_de_fila(cls, fila), materias=list(materias))

    @property
    def nombre_completo(self):
        """Nombre y apellido juntos, para mostrar en pantalla."""
        return f"{self.nombre} {self.apellido}"


@dataclass
class Curso:
    """Curso (por ejemplo "Programación 3° A") con su docente a cargo."""

    id: int
    nombre: str
    anio: int
    division: str
    docente_id: int

    @classmethod
    def desde_fila(cls, fila):
        """Crea el curso a partir de una fila de la tabla cursos."""
        return cls(**_campos_de_fila(cls, fila))

    @property
    def nombre_completo(self):
        """Nombre del curso con año y división: 'Programación 3° A'."""
        return f"{self.nombre} {self.anio}° {self.division}"


@dataclass
class Horario:
    """Bloque de clase de un curso: día, horas y materia."""

    id: int
    curso_id: int
    dia: int                # 0 = lunes ... 6 = domingo
    hora_inicio: str        # HH:MM
    hora_fin: str           # HH:MM
    materia_id: int

    @classmethod
    def desde_fila(cls, fila):
        """Crea el horario a partir de una fila de la tabla horarios."""
        return cls(**_campos_de_fila(cls, fila))

    @property
    def nombre_dia(self):
        """El día escrito: 'Lunes', 'Martes'..."""
        return DIAS[self.dia]
