# Servicio Postmaster: Status y Salud de Dominios

Este documento describe el servicio de monitoreo de salud de dominios basado en Google Postmaster, incluyendo su alcance, variables de entorno, endpoints, schemas, ejecución programada y resultados.

## 1) Alcance del servicio

El servicio cubre dos capacidades principales:

- Evaluar la salud de un dominio puntual con métricas de Google Postmaster.
- Ejecutar un batch programado para varios dominios, enviar resumen por correo y persistir el resultado para consulta histórica en dashboard.

Componentes relevantes:

- Lógica de score y semáforo: `app/services/postmaster_domain_status.py`
- Job programado + email + persistencia: `app/services/postmaster_scheduled.py`
- API HTTP del módulo: `app/api/postmaster/router.py`
- Schemas de respuesta: `app/api/postmaster/schemas.py`
- Modelo persistido: `app/models/postmaster_report.py`
- Migración de tabla: `alembic/versions/20260428135000_postmaster_reports.py`

## 2) Qué servicio abarca funcionalmente

### 2.1 Evaluación de salud de dominio (on-demand)

Entrada:

- `domain_name` (path param en endpoint)

Proceso:

- Valida dominio.
- Revisa catálogo permitido (`domains.json`) si está disponible.
- Consulta `list_traffic_stats` en Google Postmaster.
- Toma métricas recientes y calcula score interno `0-100`.
- Mapea score a status:
  - `bien` (>=80)
  - `ordinario` (>=55 y <80)
  - `mal` (<55)
- Define acción recomendada:
  - `sin_accion`
  - `monitoreo_interno`
  - `cuarentena`

Salida:

- Dominio evaluado, fecha de referencia, status, acción, resumen, score y métricas clave.

### 2.2 Reporte programado batch

Entrada:

- Lista de dominios de `worker/postmaster_domains.py` (`POSTMASTER_BEAT_DOMAIN_NAMES`)

Proceso:

- Itera todos los dominios.
- Para cada dominio intenta obtener `get_domain_status_report`.
- Acumula resultados exitosos y errores por dominio.
- Genera resumen email (texto + HTML).
- Intenta enviar correo SMTP.
- Persiste snapshot del reporte en `postmaster_reports`.

Salida:

- Payload consolidado del batch con contadores, resultados por dominio, errores y metadata de envío email.

## 3) Variables de entorno usadas

Variables del núcleo del servicio:

- `DOMAINS_REGISTRY_FILE`
  - Ruta al `domains.json` para validar dominios permitidos.

Control de agenda (Celery Beat):

- `POSTMASTER_BEAT_ENABLED`
  - Habilita/deshabilita la tarea periódica.
- `POSTMASTER_BEAT_HOUR_UTC`
  - Hora UTC del cron.
- `POSTMASTER_BEAT_MINUTE_UTC`
  - Minuto UTC del cron.
- `POSTMASTER_BEAT_DAY_OF_WEEK`
  - Días en formato crontab (`1,3,5` por defecto = lunes, miércoles, viernes).

Envío de correo del reporte:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USE_SSL`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `POSTMASTER_REPORT_TO_EMAIL`

Notas:

- Si falta `SMTP_USER` o `SMTP_PASSWORD`, el job no falla: solo marca el reporte como no enviado.
- Si falta destinatario (`POSTMASTER_REPORT_TO_EMAIL`), se omite envío y queda registro en metadata.

## 4) Endpoints del servicio

Base router: `/api/v1/postmaster`

### 4.1 GET `/domains/{domain_name}/status`

Uso:

- Consulta ad-hoc del estado de salud para un dominio.

Respuesta:

- Schema `PostmasterDomainStatusResponse`.

Errores típicos:

- `400` dominio inválido.
- `404` dominio no encontrado en catálogo o sin métricas.
- `502` error aguas arriba en Google Postmaster.

Autenticación:

- Actualmente este endpoint no exige JWT en el router actual.

### 4.2 GET `/reports`

Uso:

- Lista reportes persistidos, ordenados por `created_at` descendente.
- Acepta query `limit` (1 a 100).

Respuesta:

- `list[PostmasterReportListItem]`.

Autenticación:

- Requiere `Authorization: Bearer <token>`.

### 4.3 GET `/reports/{report_id}`

Uso:

- Obtiene detalle completo de un reporte persistido.

Respuesta:

- `PostmasterReportDetail` (incluye `payload` completo).

Autenticación:

- Requiere `Authorization: Bearer <token>`.

## 5) Schemas utilizados

Definidos en `app/api/postmaster/schemas.py`:

- `PostmasterDomainStatusResponse`
  - `domain`
  - `evaluated_date`
  - `status` (`bien|ordinario|mal`)
  - `action` (`sin_accion|monitoreo_interno|cuarentena`)
  - `summary`
  - `score`
  - `key_metrics`

- `PostmasterReportListItem`
  - `id`
  - `report_type`
  - `domains_requested`
  - `results_count`
  - `errors_count`
  - `email_sent`
  - `email_to`
  - `created_at`

- `PostmasterReportDetail` (extiende ListItem)
  - `email_error`
  - `payload` (snapshot completo de la ejecución)

Persistencia en BD (`postmaster_reports`):

- `id`
- `report_type`
- `domains_requested`
- `results_count`
- `errors_count`
- `email_sent`
- `email_to`
- `email_error`
- `payload` (JSON)
- `created_at`

## 6) Cuándo se ejecuta la tarea

La tarea periódica se registra en `worker/celery_app.py`:

- Nombre agenda: `postmaster-scheduled-domain-health`
- Tarea Celery: `worker.tasks.postmaster_scheduled_domain_health`
- Se agenda por `crontab(...)` con:
  - minuto: `POSTMASTER_BEAT_MINUTE_UTC`
  - hora: `POSTMASTER_BEAT_HOUR_UTC`
  - días: `POSTMASTER_BEAT_DAY_OF_WEEK`

Valores por defecto actuales:

- `POSTMASTER_BEAT_ENABLED=true`
- `POSTMASTER_BEAT_HOUR_UTC=14`
- `POSTMASTER_BEAT_MINUTE_UTC=30`
- `POSTMASTER_BEAT_DAY_OF_WEEK=1,3,5`

Interpretación default:

- Lunes, miércoles y viernes a las 14:30 UTC.

## 7) Resultado obtenido por ejecución

La ejecución del job retorna un objeto con esta forma conceptual:

- `ok`: true
- `domains_requested`: total dominios solicitados
- `results_count`: cantidad con evaluación exitosa
- `errors_count`: cantidad con error
- `results`: arreglo de reportes por dominio exitosos (status, action, summary, score, key_metrics, etc.)
- `errors`: arreglo de errores por dominio
- `email_sent`: si el correo fue enviado
- `email_to`: destinatario cuando aplica
- `email_error`: detalle de error si falló envío SMTP

Este resultado:

- Se usa para envío de correo (texto y HTML).
- Se persiste en `postmaster_reports.payload`.
- Se consume en frontend para el dashboard histórico de reportes.

## 8) Flujo end-to-end resumido

1. Celery Beat dispara tarea en horario configurado.
2. Se evalúa cada dominio con Google Postmaster.
3. Se consolida el payload del batch.
4. Se intenta enviar correo resumen.
5. Se persiste snapshot en BD.
6. Frontend consulta `/reports` y `/reports/{id}` para listar y ver detalle histórico.

## 9) Requisitos operativos

- Migraciones aplicadas (incluye `20260428135000_postmaster_reports.py`).
- Variables SMTP correctas para envío de correo.
- Configuración de OAuth/credenciales de Google Postmaster funcional.
- Worker Celery + Beat en ejecución.
