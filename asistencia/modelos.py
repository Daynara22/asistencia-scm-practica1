"""
modelos.py - Clases que representan las entidades del sistema.

Son clases de datos simples (dataclasses): no acceden a la base ni
validan nada. Los servicios las crean a partir de las filas de SQLite
con el método desde_fila().
"""
from dataclasses import dataclass
from typing import Optional

PRESENTE = "PRESENTE"
TARDANZA = "TARDANZA"
AUSENTE = "AUSENTE"
ESTADOS = (PRESENTE, TARDANZA, AUSENTE)


def _campos_de_fila(clase, fila):
    """Toma de la fila solo las columnas que existen en la clase."""
    claves = fila.keys()
    return {campo: fila[campo] for campo in clase.__dataclass_fields__
            if campo in claves}


@dataclass
class Usuario:
    """Cuenta para entrar al sistema (por ahora, siempre un docente)."""

    id: int
    email: str
    nombre: str
    apellido: str
    clave_hash: str = ""

    @classmethod
    def desde_fila(cls, fila):
        """Crea el usuario a partir de una fila de la tabla usuarios."""
        return cls(**_campos_de_fila(cls, fila))

    @property
    def nombre_completo(self):
        """Nombre y apellido juntos, para mostrar en pantalla."""
        return f"{self.nombre} {self.apellido}"


@dataclass
class Alumno:
    """Alumno identificado por su DNI."""

    id: int
    dni: str
    nombre: str
    apellido: str

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
