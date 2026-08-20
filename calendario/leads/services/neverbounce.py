import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def validate_email(lead):
    """Validate email via NeverBounce API. Stores result in lead.neverbounce_result."""
    if not lead.email:
        return
    if lead.neverbounce_result:
        return

    api_key = getattr(settings, 'NEVERBOUNCE_API_KEY', '')
    if not api_key:
        logger.warning('NEVERBOUNCE_API_KEY not configured, skipping validation')
        return

    start = time.time()
    try:
        resp = requests.get(
            'https://api.neverbounce.com/v4/single/check',
            params={'key': api_key, 'email': lead.email},
            timeout=10,
        )
    except requests.exceptions.ReadTimeout:
        # Conectamos, pero NeverBounce no contestó a tiempo. Esto NO es un fallo
        # transitorio: son emails de dominios que no responden a la verificación
        # SMTP, y NeverBounce agota su propio plazo interno antes que el nuestro.
        # Medido sobre 7 días de producción: de las llamadas que pasan de 8s, el
        # 99% acaban devolviendo 'unknown', así que reintentar sólo consigue el
        # mismo no-dato 30s más tarde, con un worker bloqueado mientras.
        #
        # Se registra como lo que realmente pasó —preguntamos y no hubo
        # respuesta—, que además deja el campo relleno: el CRM sólo revalida los
        # leads que le llegan sin `neverbounce_result`, y su validación va en un
        # `post_save` síncrono, así que empujarle estos casos le ralentizaría el
        # ingest sin aportar nada.
        elapsed = int((time.time() - start) * 1000)
        lead.neverbounce_result = {
            'status': 'timeout',
            'result': 'unknown',
            'is_valid': False,
            'is_rejected': False,
            'is_uncertain': True,
            'flags': [],
            'execution_time': elapsed,
        }
        lead.save(update_fields=['neverbounce_result'])
        logger.warning(
            f'[NeverBounce] Lead {lead.pk} sin respuesta en {elapsed}ms; se registra unknown'
        )
        return

    # El resto de fallos (conexión, 5xx, respuesta ilegible) sí son transitorios:
    # se dejan subir para que la tarea los reintente y los loguee según le queden
    # intentos o no. Loguearlos también aquí duplicaba el evento en Sentry.
    data = resp.json()
    result = data.get('result', 'unknown')

    lead.neverbounce_result = {
        'status': data.get('status'),
        'result': result,
        'is_valid': result in ('valid',),
        'is_rejected': result in ('invalid', 'disposable'),
        'is_uncertain': result in ('catchall', 'unknown'),
        'flags': data.get('flags', []),
        'execution_time': int((time.time() - start) * 1000),
    }
    lead.save(update_fields=['neverbounce_result'])

    logger.info(f'[NeverBounce] Lead {lead.pk} email={lead.email} result={result}')
