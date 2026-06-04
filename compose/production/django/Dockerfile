FROM python:3.12-slim

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

WORKDIR /app

COPY . /app

ENTRYPOINT ["/entrypoint"]
