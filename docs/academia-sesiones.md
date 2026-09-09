# Registro de las sesiones 1 a 1 en la academia

Esto es lo que hay que montar **en el LMS**. El lado del calendario ya está hecho
y desplegado detrás de un interruptor: en cuanto exista la mutación, se rellenan
tres variables de entorno y las sesiones empiezan a llegar.

Está escrito contra lo que el LMS ya tiene: Strawberry en `/graphql/`, API keys
por `X-API-Key` (`api/authentication.py`), y mutaciones con payload
`success` / `errors` en `api/mutations/user.py`. No hay convención nueva que
aprender: esto es un hermano de `syncBillingOrder`.

## El problema

Los profes de languages y de blogs dan clases 1 a 1. Pero las preguntas que hay
que poder responder —cuántas sesiones da cada profesor al mes, cuál es su media,
qué uso real tiene el servicio— son de gestión académica, y la gestión académica
vive en el LMS.

Se valoró que el LMS leyera el dato del calendario en vez de guardarlo, para no
duplicarlo. No sirve: el calendario mueve del orden de **500 agendas al día**,
lleva dentro todos los embudos y en algún momento habrá que limpiar reservas
viejas o la tabla no para de crecer. Un histórico académico no puede colgar de
algo que está previsto borrar.

Así que el calendario **envía** cada sesión y el LMS la guarda.

## Qué hay que montar

### 1. El modelo

Una tabla nueva. No encaja en `CalendarEvent` (`calendars/models.py`): eso es el
calendario propio del LMS —masterclases, recurrencias— y esto es el registro de
una reserva que ya ocurrió en otro sistema. Mezclarlas obligaría a que todo lo
que hoy consulta `CalendarEvent` aprenda a distinguir entre las dos.

Lo mínimo:

| Campo | Notas |
|---|---|
| `reservation_id` | `CharField(unique=True)`. Id de la reserva en el calendario. **Clave del upsert.** |
| `status` | `confirmed` / `cancelled`. Claves en inglés, como `CalendarEvent.RECURRENCE_CHOICES`. |
| `academy` | FK a `Academy`. |
| `professor` | FK a `courses.Professor`, nullable (ver más abajo). |
| `student` | FK a `accounts.UserProfile`, nullable. |
| `professor_email`, `student_email`, `student_name` | Lo que mandó el calendario, tal cual. Guardarlo aunque el FK resuelva: si mañana falla un emparejamiento, sin esto no hay forma de saber a quién era. |
| `event_type_name` | Ej. «Clase 1 a 1 de inglés». |
| `starts_at`, `ends_at` | `DateTimeField`, UTC. |
| `duration_minutes`, `student_timezone`, `booked_at`, `meet_url` | |

### 2. La mutación

En `api/mutations/`, con `permission_classes=[IsAuthenticatedWithAPIKey]` como
todas las demás:

```graphql
mutation SyncCalendarSession($input: SyncCalendarSessionInput!) {
  syncCalendarSession(input: $input) {
    success
    created
    errors
  }
}
```

El payload es el mismo patrón que `SyncBillingOrderPayload`:

```python
@strawberry.type
class SyncCalendarSessionPayload:
    success: bool
    created: bool = False
    errors: Optional[List[str]] = None
```

### 3. La entrada

Strawberry pasa snake_case a camelCase solo, así que el input se declara como el
resto (`order_id`, `academy_id`, `payment_status`):

| Campo | Tipo | Qué es |
|---|---|---|
| `reservation_id` | `str` | Id en el calendario. **Clave del upsert.** |
| `status` | `str` | `confirmed` o `cancelled`. |
| `academy_id` | `Optional[int]` | La `Academy`. Puede venir `null` — ver abajo. |
| `professor_email` | `str` | En minúsculas. |
| `professor_name` | `str` | |
| `student_lms_id` | `str` | `UserProfile.id`, del token del iframe. Vacío si la reserva no vino embebida — ver abajo. |
| `student_email` | `str` | En minúsculas. |
| `student_name` | `str` | |
| `event_type_id` | `str` | Id del tipo de evento en el calendario. |
| `event_type_name` | `str` | |
| `starts_at` | `datetime` | ISO-8601 en **UTC**. |
| `ends_at` | `datetime` | ISO-8601 en UTC. |
| `duration_minutes` | `int` | |
| `student_timezone` | `str` | Ej. `Europe/Madrid`. |
| `booked_at` | `datetime` | Cuándo se hizo la reserva. |
| `meet_url` | `str` | |

### 4. Upsert por `reservation_id`, siempre

Nunca insertar a ciegas. El calendario reintenta —Celery 3 veces, un barrido cada
tanto, y un comando de reenvío manual—, así que el mismo `reservation_id` puede
llegar varias veces. Con el upsert, repetir no duplica. Igual que
`sync_billing_order`: `created=True` si era nueva, `False` si actualizó.

### 5. Ciclo de vida: llegan altas y bajas

* **Se agenda** → llega con `status: "confirmed"`.
* **Se cancela** → llega **la misma** `reservation_id` con `status: "cancelled"`.
* **Se reagenda** → llegan **dos**: la vieja como `cancelled` y una nueva
  (`reservation_id` distinto) como `confirmed`.

Las canceladas hay que guardarlas, no borrarlas, pero **no cuentan** para
«¿cuántas sesiones dio este profesor en agosto?». Si se cuentan, el número mide
clases que nunca ocurrieron.

### 6. Si algo falla, `success: false`

GraphQL responde 200 igualmente y el calendario mira el cuerpo justo para no dar
por bueno un envío que no se guardó. Un `success: true` de mentira es la forma
silenciosa de perder el dato. El calendario lo reintenta, así que devolver el
error no pierde la sesión: la recupera en cuanto se arregle la causa.

## Los tres puntos delicados

### El profesor puede no resolverse aunque esté registrado

`Professor.user` es un `OneToOneField(null=True)`. Un `Professor` sin `user` no
tiene email y no va a emparejar con nada. Y aun teniéndolo, el email del
calendario es el corporativo del organizador (`@conquerx.com`), que no tiene por
qué ser el mismo que el de su `UserProfile` en el LMS.

Sugerencia: guardar la sesión igual, con `professor` a `null` y el
`professor_email` a la vista, y devolver `success: true` con el aviso en
`errors`... o `success: false` si preferís que el calendario reintente hasta que
el profesor esté dado de alta. **Decidilo vos y decínoslo**, porque cambia lo que
hace nuestro lado: con `false` reintentamos y encolamos alerta.

Lo que no conviene es aceptarla con `success: true` y dejarla huérfana sin rastro.

### El alumno se empareja por `student_lms_id`, que es `UserProfile.id`

En `system/calendar_embed.py` (rama `cl/embeded-appointment-booking`) el token se
firma así:

```python
token = dumps(
    {"uid": user.id, "email": user.email, "nombre": user.full_name, ...},
    key=settings.CALENDAR_EMBED_SECRET,
    salt=settings.CALENDAR_EMBED_SALT,
)
```

Ese `uid` es el `accounts.UserProfile.id`. El calendario lo guarda al crear la
reserva y os lo devuelve tal cual en `student_lms_id`, así que el emparejamiento
es un `UserProfile.objects.get(pk=...)`, no una búsqueda por email.

**Emparejad por ahí, con el email solo como respaldo.** El `student_email` de una
reserva embebida sale del mismo token, pero el de una reserva hecha por el enlace
público lo escribe la persona a mano y puede no ser el de su cuenta.

Dos consecuencias prácticas:

* Mientras la rama del iframe no esté mergeada y desplegada, `student_lms_id`
  llega vacío y solo queda el email. Cuando se despliegue, empieza a llegar solo
  sin tocar nada de este contrato.
* Los tipos de evento que se registran en la academia **no** son solo los tres
  que se embeben. La casilla está en todos los tipos de evento del calendario y
  se irá marcando lo que interese medir. En los que no se embeben nunca habrá
  `student_lms_id`: ahí el emparejamiento por email es lo único que hay, y para
  algunos ni siquiera habrá alumno del LMS al otro lado. Guardad la sesión igual;
  las métricas de profesor siguen valiendo.

### `academy_id` puede venir null

El LMS es multi-academia y todas vuestras mutaciones piden `academy_id`. Desde el
calendario no siempre se puede deducir: el `school_code` que usan las demás
integraciones sale del funnel o del Lead, y una clase 1 a 1 no tiene ninguno de
los dos. Así que se configura a mano en cada tipo de evento.

Si nos pasás los ids de las `Academy` los rellenamos y siempre viajará puesto. Se
deja opcional para que la integración no se quede parada esperando ese dato: con
`null`, resolvedlo por el profesor.

## Ejemplo completo

```http
POST /graphql/ HTTP/1.1
Host: <la academia>
Content-Type: application/json
X-API-Key: <la clave>
```

```json
{
  "operationName": "SyncCalendarSession",
  "query": "mutation SyncCalendarSession($input: SyncCalendarSessionInput!) { syncCalendarSession(input: $input) { success created errors } }",
  "variables": {
    "input": {
      "reservationId": "48213",
      "status": "confirmed",
      "academyId": 7,
      "professorEmail": "profesor@conquerx.com",
      "professorName": "Ana López",
      "studentLmsId": "",
      "studentEmail": "alumna@example.com",
      "studentName": "Carmen Ruiz",
      "eventTypeId": "17",
      "eventTypeName": "Clase 1 a 1 de inglés",
      "startsAt": "2026-09-15T14:00:00+00:00",
      "endsAt": "2026-09-15T14:45:00+00:00",
      "durationMinutes": 45,
      "studentTimezone": "Europe/Madrid",
      "bookedAt": "2026-09-09T09:12:44+00:00",
      "meetUrl": "https://meet.google.com/abc-defg-hij"
    }
  }
}
```

## Lo que viene después: el feedback del alumno

La idea es que unos minutos después de terminar la sesión le llegue al alumno un
correo pidiéndole su opinión del profesor. Eso se hace **entero en el LMS** y no
necesita nada más del calendario: con `ends_at`, el alumno y el profesor ya se
puede programar el envío y colgar la puntuación de la sesión. Por eso `ends_at`
va en el payload aunque para contar sesiones bastaría con `starts_at`.

Ojo con lo de arriba: mientras el alumno se empareje por email, ese correo se le
manda a lo que la persona escribió al reservar, no a su cuenta del LMS.

## El lado del calendario (hecho)

* Se envía solo lo de los tipos de evento marcados con **«Registrar las sesiones
  en la academia»** en el panel. La casilla está en **todos** los tipos de
  evento, no solo en los embebidos, y se irá marcando lo que interese: un webinar
  embebido no es gestión académica, y hay sesiones que sí lo son sin estar
  embebidas. En el admin hay acciones para marcarlos en lote.
* Envío asíncrono (Celery), 3 reintentos con backoff. Una academia caída **nunca**
  impide que un alumno reserve su clase.
* Un barrido revisa cada tanto las reservas de las últimas 24 h y reencola las
  que no llegaron, distinguiendo el alta de la cancelación.
* Para lo más viejo que eso —una caída larga— hay un comando de reenvío de un
  rango concreto. Exige `--desde` a propósito: es para tapar huecos, no para
  subir el histórico.

  ```bash
  python manage.py enviar_sesiones_academia --desde 2026-09-10 --dry-run
  python manage.py enviar_sesiones_academia --desde 2026-09-10
  ```

* Estado por reserva visible en el admin: columna **Academia** (✅ enviada /
  ⚠️ fallida con enlace a Sentry / ⏳ pendiente / — no aplica).

### Variables de entorno

```
ACADEMIA_ENABLED=True
ACADEMIA_GRAPHQL_URL=https://<la academia>/graphql/
ACADEMIA_API_KEY=<la clave>
```

Sin `ACADEMIA_ENABLED`, o sin URL y clave, cada envío hace no-op y lo deja en el
log. Se puede desplegar antes de que exista la mutación sin que pase nada.

## Cómo probamos que las dos partes se entienden

1. Daniel monta la mutación y crea una `APIKey` para el calendario.
2. Ponemos URL y clave en pruebas y marcamos un tipo de evento de prueba.
3. Se agenda una sesión de mentira; tiene que aparecer en el LMS.
4. Se cancela; la misma fila tiene que pasar a `cancelled`.
5. Se reagenda; tienen que quedar dos filas, una cancelada y una confirmada.
6. Con eso en verde, se marcan los tipos de evento reales y las sesiones se van
   registrando a partir de ese momento.

**No se sube el histórico.** Las reservas anteriores a la integración se quedan
donde están; el recuento arranca el día que se enciende. Si más adelante hiciera
falta alguna de antes, se puede reenviar un rango con el comando, pero no es el
plan.
