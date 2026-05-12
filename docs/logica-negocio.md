# Lógica de Negocio — Conquer Calendario

## Contexto

Microservicio interno de agendamiento. Sustituye a Calendly (~36.000 €/año).
Primer caso de uso: academia de inglés. Si funciona, se extiende a las demás academias del ecosistema Conquer.

## Actores

- **Host** — closer / setter / admin de la academia. Tiene cuenta en el sistema, configura su disponibilidad, recibe reservas. Los hosts son importados por el admin (no se registran solos); su acceso es exclusivamente por Google OAuth.
- **Lead (público)** — persona externa que recibe un enlace de reserva. No tiene cuenta. Solo ve la página pública del host/event-type.
- **Admin del calendario** — gestiona usuarios, roles, event types globales.

## Flujo principal

```
Admin importa hosts con: python manage.py importar_hosts --emails user@conquerx.com
          ↓
Host configura su disponibilidad semanal y tipos de evento desde /panel/
          ↓
Sistema genera enlace público: /r/<user-slug>/<event-slug>/
          ↓
Lead recibe enlace (vía CRM / email / setter)
          ↓
Lead abre página → ve días/horas disponibles → elige slot → completa formulario
          ↓
Sistema crea reserva → consulta FreeBusy de Google → crea evento en Google Calendar con Meet link
          ↓
Google notifica al host e invitado por email
          ↓
(Fase 06) Sistema notifica al CRM vía webhook → CRM crea registro Schedule
```

## Reglas transversales

- **Login obligatorio** para cualquier ruta del panel interno. Solo mediante Google OAuth (`/accounts/google/login/`). Los hosts no tienen contraseña usable.
- **Bloqueo de acceso**: `ConquerSocialAccountAdapter` bloquea usuarios no importados o con `is_active=False`. No hay auto-registro.
- **Página pública** (`/<user-slug>/<event-slug>/`) no requiere login.
- **Zona horaria**: todo se almacena en UTC. El host configura su tz en el perfil. Los slots de disponibilidad (`hora_inicio`, `hora_fin`) son naïve y se interpretan en `host.timezone`.
- **Buffer y aviso mínimo**: cada event-type configura buffer entre reuniones (`buffer_antes_minutos`, `buffer_despues_minutos`) y tiempo mínimo de antelación (`aviso_minimo_horas`).

## Cálculo de slots disponibles (`calcular_slots`)

```
Para cada día en el rango [fecha_desde, fecha_hasta]:
  Para cada BloqueHorarioSemanal del host que coincida con el día de semana:
    Convertir hora_inicio / hora_fin a UTC (usando host.timezone)
    Si el bloque cruza un cambio de DST → descartarlo
    Generar slots de duracion_minutos dentro del bloque (step = duracion + buffer)
    Para cada slot:
      Si inicio_slot < ahora + aviso_minimo_horas → descartar
      Si hay Reserva CONFIRMADA del host que colisione → descartar
      → slot disponible
```

## Concurrencia de reservas

- `crear_reserva` ejecuta dentro de `transaction.atomic()`.
- Lock: `EventType.objects.select_for_update().get(pk=id)` — serializa todos los bookings del mismo event_type.
- Re-validación completa del slot dentro de la transacción.
- `UniqueConstraint(host, inicio_utc) WHERE estado='confirmada'` como guardrail de BD.

## Round-robin — algoritmo `least-loaded`

```
Dado inicio_utc y un EventType con pool de N hosts:
  1. candidatos = hosts del pool con is_active=True y el slot disponible en su horario
  2. Si candidatos vacío → SlotNoDisponibleError
  3. counts[h] = reservas CONFIRMADAS del host para este event_type
  4. Ordenar por (counts[h] ASC, pivot_id ASC)  ← tiebreak determinista
  5. Asignar al primero
```

`EventType.host` = owner (slug URL, CRUD). El pivot `event_types_x_hosts` es la fuente de verdad del pool.

## Integración Google Calendar (Fase 05)

### Service Account + Domain-Wide Delegation

- Service account: `conquer-crm@conquer-crm-meetings.iam.gserviceaccount.com`.
- DWD aprobado en Google Workspace Admin Console una sola vez — cubre todos los hosts del dominio automáticamente.
- Impersonación: `Credentials.from_service_account_file(...).with_subject(host.email)`.
- Sin UI de "conectar Google". Sin tokens en BD. El JSON de la service account se monta como volumen read-only.

### FreeBusy anti double-booking

- Antes de persistir la reserva, se consulta `freebusy.query` sobre todos los calendarios visibles del host.
- **Fail-open**: si Google falla (timeout, 5xx, 403), devuelve `False` y no bloquea la reserva.

### Creación de evento (`transaction.on_commit`)

- Se ejecuta post-commit, fuera del lock sobre `EventType`.
- `conferenceDataVersion=1` → genera Google Meet link automáticamente.
- `sendUpdates='all'` → Google notifica al host e invitado por email.
- `requestId=str(reserva.confirmacion_token)` → idempotente ante reintentos.
- Si falla → `google_sync_estado='error'`. La reserva queda confirmada sin Meet link.

### Cancelación de evento

- Solo se llama si `reserva.google_event_id` está poblado.
- `HttpError 404/410` → éxito (idempotente).
- `sendUpdates='all'` → Google notifica la cancelación.

## Aislamiento panel vs público

- **Panel** (`/panel/...`): protegido por `RequierePermisoMixin`. Toda query filtra por `host=request.user`. Para ver datos de otros hosts, usar `/admin/`.
- **Público** (`/<user_slug>/<event_slug>/`, `/r/<token>/`): sin login, sin IDs incrementales expuestos, 404 silencioso si host/event_type no existe o está inactivo.

## Restricciones / no-objetivos

- No es un sistema de pagos.
- No reemplaza al CRM como fuente de verdad de leads — solo notifica reservas via webhook.
- MVP: solo Google Calendar + Meet. Sin Outlook ni Zoom.
- Sin aleatoriedad en el round-robin — función pura del estado de BD.
