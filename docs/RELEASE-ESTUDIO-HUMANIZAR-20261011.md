# Estudio Humanizar: corrección desplegada y prueba visual

Entrega del 11 de octubre de 2026, 20:19 UTC. Recibo saneado:
`RELEASE-ESTUDIO-HUMANIZAR-20261011.json`. Complementa, sin sustituir, el recibo
anterior de familia y las escrituras de referencias de las 19:56 UTC.

## Resultado

Código `e956d37eba50291f7a07838d0fddebbff5ca436b`, revisión
`eikon-00060-kkl`, 100% del tráfico y sin tags. OCI index
`sha256:a4ba5ff8d89030569967cad0f418aaadeb813a9f282d26c5a8f5cc2947d5d4a3`;
manifest linux/amd64 efectivo
`sha256:a3199ab424897f16fa5e5011361e5cd404e247d6774e98678027bd5a82c5dc04`,
comprobado como miembro del index. Nueve archivos runtime coinciden con el
checkout; los dos orígenes Cloud Run y Vercel sirven la SPA exacta de la imagen.
Recursos, variables, secretos, red, permisos del servicio y bucket se conservaron.

El Estudio limpiaba la pieza previa al cambiar de marca, pero mantenía los
textos escritos para el producto anterior. Ahora limpia también esos textos.
Editar un campo invalida el PNG y su descarga; durante el render, marca, tipo
y campos permanecen bloqueados para conservar el contexto de la pieza.
No se atribuye a esta corrección cancelación de renders al desmontar la página.

El navegador real local verificó los tres comportamientos. Aletheia y Prizma
conservaron sus logos originales y produjeron PNGs completos de 2160×2700,
con pie, sitio y contenido propio. SHA Aletheia
`485749a891ebe00d07ce1d5321bfa7defb3d15cd5248008c49b392eacf9c4db9`;
SHA Prizma `64e19f75ff2e8e409d6f4c8c9a879608e2a740b0d78cd498712815f7199c04c1`.
El observador de descarga Aletheia agotó 15s; el archivo nuevo producido por
el clic se localizó y se inspeccionó por dimensiones, hash y píxeles.

Frontend: **78 pruebas aprobadas**, build TypeScript/Vite correcto y revisión
independiente sin bloqueantes. Dos pruebas nuevas fallaron antes de corregir
los handlers. El delta tuvo gitleaks sin hallazgos. El core de familia/exportación
mantiene su verificación previa de 47 pruebas; no se presenta una nueva suite
Python global para esta corrección exclusiva del frontend.

El respaldo fresco de 112504 bytes se restauró en un clon PostgreSQL sin red.
Doble init_db conserva filas y columnas. La revisión anterior 59 queda registrada
para rollback. Tras desplegar, la API owner de tenant17 sigue funcionando;
marcas anónimas rechaza con 401. Las quince versiones y perfiles Humanizar
se conservaron y las doce referencias recuperadas coinciden por SHA.

## Límites y siguiente entrega

Los PNGs son QA local con cuenta sintética; no piezas aprobadas ni publicaciones.
La GUI de producción aún espera el login del operador en la pestaña preparada.
Quedan tres referencias por decidir: Deméter, Gravitatoria y Práxis. No se
seleccionaron iconos genéricos o de cliente como masters exclusivos.

Facebook Systems, Facebook Humanizar e Instagram News pasaron preflight
GET-only de cuenta y permisos. Este resultado no prueba renovación futura ni
publicación nueva. El inventario registra tres bases heredadas, nueve envíos
históricos, ocho pendientes retenidos y cuatro retiradas; todavía requiere
conciliar cinco posts manuales antes de afirmar historial completo.

No hubo nuevos medios aprobados, envíos sociales, importación del historial,
reactivación de timers ni cambios de credenciales. Campañas, conexiones
multiempresa, revisión completa, calendario, worker y panel aún no se implementan;
siguen pendientes de revisar el diseño escrito y preparar el plan.
