# ─────────────────────────────────────────────────────────────
# Etapa 1: build del frontend (React/Vite) con Node.
# Genera /app/frontend/dist dentro de la imagen — el server NO
# necesita Node ni un dist commiteado.
# ─────────────────────────────────────────────────────────────
FROM node:20-slim AS frontend

# DSN de Sentry para el frontend; Vite lo embebe en el bundle en build time.
# Vacío por defecto → Sentry deshabilitado en el bundle.
ARG VITE_SENTRY_DSN=
ENV VITE_SENTRY_DSN=${VITE_SENTRY_DSN}

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# Bundle de servidor para el SSR del funnel (dist-ssr/funnel-ssr.js).
RUN npm run build:ssr


# ─────────────────────────────────────────────────────────────
# Etapa 2: runtime Django (sin Node).
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS django

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    locales \
    && sed -i '/es_ES.UTF-8/s/^# //g' /etc/locale.gen \
    && locale-gen \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements /requirements
RUN pip install --upgrade pip \
    && pip install -r /requirements/prod.txt

COPY ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//' /entrypoint && chmod +x /entrypoint

COPY ./compose/production/django/start /start
RUN sed -i 's/\r$//' /start && chmod +x /start

COPY ./compose/production/django/start-celeryworker /start-celeryworker
RUN sed -i 's/\r$//' /start-celeryworker && chmod +x /start-celeryworker

COPY ./compose/production/django/start-celerybeat /start-celerybeat
RUN sed -i 's/\r$//' /start-celerybeat && chmod +x /start-celerybeat

WORKDIR /app

COPY . /app

# Trae el frontend ya compilado desde la etapa Node (frontend/dist está
# en .dockerignore, así que esta es la única fuente del dist en la imagen).
COPY --from=frontend /app/frontend/dist /app/frontend/dist

ENTRYPOINT ["/entrypoint"]


# ─────────────────────────────────────────────────────────────
# Etapa 3: servicio Node SSR del funnel.
# Renderiza los componentes React (renderToString) que Django consume vía
# POST /render. jsdom (isomorphic-dompurify) no se puede bundlear, así que el
# bundle externaliza las deps y este runtime corre con node_modules.
# ─────────────────────────────────────────────────────────────
FROM node:20-slim AS node-ssr
ENV NODE_ENV=production
WORKDIR /app/frontend
COPY --from=frontend /app/frontend/node_modules ./node_modules
COPY --from=frontend /app/frontend/dist-ssr ./dist-ssr
COPY --from=frontend /app/frontend/server ./server
EXPOSE 3000
CMD ["node", "server/ssr-server.mjs"]
