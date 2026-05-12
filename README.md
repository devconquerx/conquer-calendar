# Conquer Calendario

Microservicio interno de agendamiento — alternativa a Calendly (~36.000 €/año) para el ecosistema Conquer.

Primer caso de uso: academia de inglés. Si funciona, se extiende al resto.

## Stack

- Python 3.12 + Django 4.2 + DRF
- PostgreSQL 16
- Docker Compose (desarrollo local)
- Google Calendar API + Google Meet (Service Account + Domain-Wide Delegation)
- `django-allauth` con Google OAuth (login exclusivo para hosts)

## Levantar en local

```bash
# Primera vez
docker compose -f local.yml up --build

# Migraciones
docker compose -f local.yml run --rm django python manage.py migrate

# Crear superusuario
docker compose -f local.yml run --rm django python manage.py createsuperuser
```

**Puertos:**
- Django: `http://localhost:8002`
- PostgreSQL: `localhost:5434`

**Health check:** `http://localhost:8002/health/`

## Variables de entorno

El proyecto usa dos archivos de entorno en `.envs/.local/`. Ya existen los ejemplos en el repo:

```bash
cp .envs/.local/.django.example .envs/.local/.django
cp .envs/.local/.postgres.example .envs/.local/.postgres
```

Edita `.django` y rellena:

- `CALENDARIO_DJANGO_SECRET_KEY` — cualquier cadena larga y aleatoria
- `GOOGLE_SERVICE_ACCOUNT_FILE` — ruta al JSON de la service account dentro del contenedor (se monta como volumen en `docker-compose`)
- `GOOGLE_AUTH_CLIENT_ID` / `GOOGLE_AUTH_CLIENT_SECRET` — credenciales OAuth de Google Cloud Console. Redirect URI autorizado: `http://localhost:8002/accounts/google/login/callback/`

En `.postgres` cambia `POSTGRES_PASSWORD` / `CALENDARIO_POSTGRES_PASSWORD` por una contraseña segura.

Los archivos reales (`.django`, `.postgres`) están en `.gitignore` y nunca se suben al repo.

## Importar hosts

Los hosts no se registran solos — el admin los importa con el management command:

```bash
# Uno o varios emails
docker compose -f local.yml run --rm django python manage.py importar_hosts \
    --emails santiago.tovar@conquerx.com otro@conquerx.com

# Desde CSV (columna "email")
docker compose -f local.yml run --rm django python manage.py importar_hosts \
    --csv /ruta/al/archivo.csv

# Todos los usuarios activos de un dominio Google Workspace
docker compose -f local.yml run --rm django python manage.py importar_hosts \
    --dominio conquerx.com --admin admin@conquerx.com
```

El comando es idempotente. Crea el usuario con contraseña inutilizable, asigna el rol `host` y activa la cuenta. El host puede loguearse a partir de entonces con Google OAuth.

## Ejecutar tests

```bash
docker compose -f local.yml run --rm django python manage.py test tests
```

33 tests cubriendo: creación de reservas, cancelación, cálculo de slots, integración Google Calendar, adaptador de autenticación e importación de hosts.

## Documentación técnica

- [`docs/modelo-datos.md`](docs/modelo-datos.md) — esquema completo de la base de datos
- [`docs/logica-negocio.md`](docs/logica-negocio.md) — flujos, reglas y decisiones de diseño

## Estructura del proyecto

```
calendario/
  users/              # Usuarios (hosts), roles, permisos, importación
  event_types/        # Tipos de evento + pivot round-robin
  availability/       # Bloques horarios semanales
  bookings/           # Reservas + servicio de slots
  google_calendar/    # Integración Calendar API (sin modelos propios)
  _templates/         # Templates HTML del panel y páginas públicas
config/
  settings/           # base / local / prod
  urls.py
tests/
  factories.py        # Helpers reutilizables para todos los tests
  bookings/
  google_calendar/
  users/
docs/                 # Modelo de datos y lógica de negocio (comprometido)
```

## Estado de fases

| Fase | Descripción                              | Estado       |
|------|------------------------------------------|--------------|
| 01   | Panel interno + autenticación Google SSO | Implementada |
| 02   | Tipos de evento y disponibilidad         | Implementada |
| 03   | Sistema de reservas (página pública)     | Implementada |
| 04   | Round-robin entre hosts                  | Implementada |
| 05   | Google Calendar + Google Meet            | Implementada |
| 06   | Webhooks salientes al CRM                | Pendiente    |
