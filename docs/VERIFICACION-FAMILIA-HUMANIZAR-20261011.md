# Familia Humanizar: verificación de código y límites

## Alcance

Perfil explícito `texts.brand_family="humanizar"`, corrección de estados de
identidad y acceso al formato `social_4x5` desde Estudio. No incluye campañas,
conexiones OAuth, calendario ni un nuevo trabajador de publicaciones.

Los originales mantienen bytes y SHA. Si no existe logo original ni identidad
procedural fijada, no se fabrica un isotipo. El adaptador web y el trabajador
usan la marca de su empresa al seleccionar el perfil, aunque su slug coincida
con un archivo histórico. Otros perfiles conservan su ruta anterior.

## Evidencia

| Comprobación | Resultado | Límite |
|---|---|---|
| Suite Python completa, PostgreSQL 16 sintético y SQLite | 867 aprobadas, 2 omitidas | Las dos omisiones requieren outputs de demostración ausentes |
| Familia y plan HTTP finales, con PostgreSQL | 45 aprobadas | No es inspección de píxeles |
| Frontend Node, consumidores TS reales | 67 aprobadas | No sustituye generación en navegador |
| TypeScript y Vite | Correcto | Build local |
| Ruff de archivos cambiados nuevos y mypy focal | Correcto | Worker conserva diez RUF036 preexistentes |
| Revisión independiente, tres rondas | Aprobado sin bloqueantes nuevos | Retícula 12 real sólo en social_4x5 |
| Navegador, cuenta sintética local | Acceso y badges de tres marcas correctos | Generación y descarga pendientes por panel de extensión |
| Respaldo privado de producción | Dump fresco, 112053 bytes, configuración e IAM preservados | Restauración no ensayada; no acredita despliegue |

La prueba HTTP final comprueba creación 202, plan 200, formato 1080×1350,
plantilla accesible con autenticación y otro tenant rechazado con 404. También
comprueba títulos propios y ausencia de estadísticas ficticias. Las variables
de cuatro y ocho columnas no se presentan como layouts responsive terminados.

## Pendientes de aceptación

1. Reanudar CUA al cerrar el panel de la extensión; generar la pieza vertical,
   comprobar fuente, retícula, ausencia de desbordamientos y logo horizontal,
   y descargar su PNG.
2. Sólo tras ese gate, actualizar la imagen del servicio existente y comprobar
   SHA/digest, configuración, API y recorrido real. Mantener cola antigua parada.
3. Aplicar el perfil a las marcas Humanizar con nuevas revisiones de piezas;
   no aprobar automáticamente borradores ni borrar versiones previas.

Los nuevos módulos del centro se describen en el diseño del 11 de octubre y
requieren su revisión escrita antes del plan. La meta permanece activa.
