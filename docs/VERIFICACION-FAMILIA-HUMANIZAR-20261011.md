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
| Frontend Node final, consumidores TS reales y geometría | 78 aprobadas | Incluye limpieza de contenido entre productos, invalidación de PNG y bloqueo de controles durante render |
| Core de familia y exportaciones finales | 47 aprobadas | Incluye 16 del exportador; deltas posteriores a la suite general, sin nueva corrida global |
| TypeScript y Vite | Correcto | Build local |
| Ruff de archivos cambiados nuevos y mypy focal | Correcto | Worker conserva diez RUF036 preexistentes |
| Revisión independiente, cinco rondas | Aprobado sin bloqueantes nuevos | Retícula 12 real sólo en social_4x5 |
| Navegador, cuenta sintética local | Acceso, badges, PNG final 2160×2700 completo, móvil390×844, casos Agentes/Cauce/Aletheia/Prizma | No todos los formatos |
| GUI autenticada de producción | Sesión Humanizar existente, estados de las marcas, render/descarga Prizma, lote2495 y variación3048; bytes iguales al PNG descargado | Desktop y social_4x5; sin aprobación editorial ni publicación |
| Respaldo privado de producción | Dump fresco, 112504 bytes, restauración en clon sin red y doble init_db sin modificar filas/columnas | No acredita despliegue |
| Imagen y servicio desplegado | e956d37 / eikon-00060-kkl al100%, configuración y permisos conservados | Recibos históricos y corrección actual en RELEASE-ESTUDIO-HUMANIZAR-20261011.md |

La prueba HTTP final comprueba creación 202, plan 200, formato 1080×1350,
plantilla accesible con autenticación y otro tenant rechazado con 404. También
comprueba títulos propios y ausencia de estadísticas ficticias. Las variables
de cuatro y ocho columnas no se presentan como layouts responsive terminados.

## Pendientes de aceptación

1. Resolver la referencia de Práxis. Los quince perfiles están aplicados y
   catorce logos fijados, incluidos Deméter y Gravitatoria110/119v4. Sus lockups
   UI existentes se verificaron en páginas vigentes; ambos PNG2160×2700 fueron
   generados, descargados e inspeccionados en producción.
   Aletheia/Prizma tienen comparación local de fuentes, lectura API/MCP y PNG
   final descargado e inspeccionado en Estudio local.
2. Emitir nuevos briefs y revisar piezas contra las versiones actuales;
   no aprobar automáticamente borradores ni borrar versiones previas.

Los nuevos módulos del centro se describen en el diseño del 11 de octubre y
requieren su revisión escrita antes del plan. La meta permanece activa.

La prueba GUI de producción se cerró el 11 de octubre usando la sesión que ya
estaba abierta en eikon.humanizar.cloud. Se recargó la pestaña antigua y mostró
los estados actualizados; no se copiaron cookies o credenciales entre dominios.
Ver el seguimiento GUI en `RELEASE-ESTUDIO-HUMANIZAR-20261011.json`.
