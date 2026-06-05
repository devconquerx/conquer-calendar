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

    except Exception as e:
        logger.error(f'[NeverBounce] Lead {lead.pk} error: {e}')
        raise
