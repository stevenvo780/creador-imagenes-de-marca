# Metodología de auditoría

## Severidades

- **critical**: bloquea release; datos corruptos, seguridad rota o render imposible.
- **major**: release posible solo con aceptación explícita; visual/WCAG con impacto.
- **minor**: deuda corregible sin bloquear.
- **note**: observación sin acción inmediata.

## Regla de evidencia

Un hallazgo debe tener comando, ruta o reporte. Si no tiene evidencia reproducible, queda como hipótesis.

## Remediación

Toda remediación debe ser verificable con un gate o con un comando concreto.
