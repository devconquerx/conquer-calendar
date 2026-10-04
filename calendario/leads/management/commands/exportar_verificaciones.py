"""Vuelca a JSONL todas las verificaciones de email que guarda el calendario.

La verificación de emails pasa a ser cosa de Relay: el calendario deja de
validar, de guardar veredictos y de decidir nada con ellos. Antes de borrar la
caché (`email_verification_cache`) y el campo `Lead.neverbounce_result`, este
comando saca todo lo que hay para que Relay lo herede.

Una línea JSON por veredicto, con dos orígenes:

- `cache`: una fila de `email_verification_cache` (sondeo SMTP propio).
- `lead`: el `neverbounce_result` de un lead (sondeo propio, caché o NeverBounce).

Campos comunes: origen, email (en minúsculas y sin espacios), result, reason,
flags, source, fecha (ISO 8601). El resto de lo guardado va en `extra` para no
perder nada.

Orden de despliegue: este comando se despliega y se ejecuta ANTES de la
migración que borra la tabla y el campo. Ejemplo:

    python manage.py exportar_verificaciones --salida /tmp/verificaciones.jsonl
"""
import json
import sys

from django.core.management.base import BaseCommand
from django.db import connection


def _normalizar(email):
    return (email or '').strip().lower()


def _iso(fecha):
    return fecha.isoformat() if fecha else None


class Command(BaseCommand):
    help = ('Exporta a JSONL la caché de verificaciones de email y los '
            'Lead.neverbounce_result, para que Relay los herede.')

    def add_arguments(self, parser):
        parser.add_argument('--salida', '-o', default='-',
                            help='Fichero JSONL de salida ("-" = salida estándar, por defecto).')
        parser.add_argument('--solo', choices=('cache', 'leads'),
                            help='Exporta solo uno de los dos orígenes.')

    def handle(self, *args, **opts):
        salida = opts['salida']
        fh = sys.stdout if salida == '-' else open(salida, 'w', encoding='utf-8')
        try:
            n_cache = n_leads = 0
            if opts['solo'] in (None, 'cache'):
                n_cache = self._exportar_cache(fh)
            if opts['solo'] in (None, 'leads'):
                n_leads = self._exportar_leads(fh)
        finally:
            if fh is not sys.stdout:
                fh.close()

        # El resumen va a stderr para no ensuciar el JSONL cuando sale por stdout.
        self.stderr.write(self.style.SUCCESS(
            f'Exportadas {n_cache} filas de la caché y {n_leads} veredictos de leads'
            + ('' if salida == '-' else f' en {salida}')
        ))

    @staticmethod
    def _escribir(fh, registro):
        fh.write(json.dumps(registro, ensure_ascii=False, default=str) + '\n')

    def _exportar_cache(self, fh):
        # SQL directo y no el modelo: así el comando sigue sirviendo aunque el
        # modelo ya no exista en el código, mientras la tabla siga en la BD.
        if 'email_verification_cache' not in connection.introspection.table_names():
            self.stderr.write('La tabla email_verification_cache no existe; se omite.')
            return 0

        n = 0
        with connection.cursor() as cur:
            cur.execute(
                'SELECT email, result, reason, smtp_code, smtp_message, created, '
                'modified, expires_at, hit_count FROM email_verification_cache ORDER BY id'
            )
            while True:
                filas = cur.fetchmany(2000)
                if not filas:
                    break
                for (email, result, reason, smtp_code, smtp_message, created,
                     modified, expires_at, hit_count) in filas:
                    self._escribir(fh, {
                        'origen': 'cache',
                        'email': _normalizar(email),
                        'result': result,
                        'reason': reason or '',
                        'flags': [],
                        'source': 'own_smtp',
                        'fecha': _iso(modified or created),
                        'extra': {
                            'smtp_code': smtp_code,
                            'smtp_message': smtp_message or '',
                            'created': _iso(created),
                            'expires_at': _iso(expires_at),
                            'hit_count': hit_count,
                        },
                    })
                    n += 1
        return n

    def _exportar_leads(self, fh):
        with connection.cursor() as cur:
            columnas = {c.name for c in connection.introspection.get_table_description(cur, 'leads')}
        if 'neverbounce_result' not in columnas:
            self.stderr.write('El campo leads.neverbounce_result no existe; se omite.')
            return 0

        n = 0
        with connection.cursor() as cur:
            cur.execute(
                'SELECT id, email, neverbounce_result, created FROM leads '
                'WHERE neverbounce_result IS NOT NULL ORDER BY id'
            )
            while True:
                filas = cur.fetchmany(2000)
                if not filas:
                    break
                for lead_id, email, resultado, created in filas:
                    if isinstance(resultado, str):
                        resultado = json.loads(resultado)
                    resultado = resultado or {}
                    if not email or not resultado:
                        continue
                    extra = {k: v for k, v in resultado.items()
                             if k not in ('result', 'reason', 'flags', 'source')}
                    extra['lead_id'] = lead_id
                    self._escribir(fh, {
                        'origen': 'lead',
                        'email': _normalizar(email),
                        'result': resultado.get('result', 'unknown'),
                        'reason': resultado.get('reason', '') or '',
                        'flags': resultado.get('flags') or [],
                        # Los primeros veredictos (solo NeverBounce) no guardaban
                        # `source`: el sondeo propio llegó después y sí lo pone.
                        'source': resultado.get('source') or 'neverbounce',
                        'fecha': _iso(created),
                        'extra': extra,
                    })
                    n += 1
        return n
