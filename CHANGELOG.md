# Changelog
## [2.1.0] - 2026-09-10
### Added
- Función `obtener_reporte_estadistico` para extraer resumen de métricas e historial de asistencias.

## [2.0.1] - 2026-09-10
### Fixed
- Manejo de excepciones y validación de tipos nulos para el campo DNI en `registrar_asistencia`.

## [2.0.0] - 2026-09-05
### Changed
- BREAKING: registrar_asistencia ahora recibe un diccionario con metadatos del alumno (dni, materia) en lugar de un string plano.

## [1.1.0] - 2026-09-03
### Added
- Acumulador y contador global de asistencias en tiempo de ejecucion.

## [1.0.1] - 2026-08-20
### Fixed
- Eliminacion de espacios en blanco en el DNI escaneado.

## [1.0.0] - 2026-08-01
### Added
- Lanzamiento inicial con validacion basica de DNI.
