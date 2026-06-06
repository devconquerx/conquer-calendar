import logging

import requests
from django.conf import settings

from .utils import SCHOOL_SLUG_TO_CODE

logger = logging.getLogger(__name__)

MAILGUN_API_URL = 'https://api.mailgun.net/v3'

# Per-school email configuration
SCHOOL_EMAIL_CONFIG = {
    'cb': {
        'domain': 'conquerblocks.com',
        'from': 'Bienve <bienvenido.saez@conquerblocks.com>',
        'subject': 'Aquí tienes la clase que me pediste',
        'template': 'clase cb plain',
    },
    'cl': {
        'domain': 'conquerlanguages.com',
        'from': 'Andy <andy.povedano@conquerlanguages.com>',
        'subject': 'Aquí tienes la clase que me pediste',
        'template': 'clase cl plain',
    },
    'cf': {
        'domain': 'conquerfinance.es',
        'from': 'Felix <felix.fuertes@conquerfinance.es>',
        'subject': 'Aquí tienes la clase que me pediste',
        'template': 'clase cf plain',
    },
    'fi': {
        'domain': 'conquerfinance.es',
        'from': 'Felix <felix.fuertes@conquerfinance.es>',
        'subject': 'Aquí tienes la clase que me pediste',
        'template': 'clase cf plain',
    },
}


def _get_school_code(lead):
    """Extract 2-letter school code from lead."""
    school = (lead.school or '').lower().strip()
    if school in SCHOOL_SLUG_TO_CODE:
        return SCHOOL_SLUG_TO_CODE[school]
    funnel = (lead.funnel or '').lower()
    for code in ('cb', 'cl', 'cf', 'fi'):
        if code in school or code in funnel:
            return code
    return None


def send_welcome_email(lead):
    """Send welcome email to lead via Mailgun using school-specific template."""
    api_key = getattr(settings, 'MAILGUN_API_KEY', '')
    if not api_key:
        raise RuntimeError(f'MAILGUN_API_KEY not configured, cannot send email for lead {lead.pk}')

    if not lead.email:
        logger.warning('[Mailgun] Lead %s has no email, skipping', lead.pk)
        return False

    school_code = _get_school_code(lead)
    config = SCHOOL_EMAIL_CONFIG.get(school_code)
    if not config:
        raise RuntimeError(f'No email config for school code "{school_code}", lead {lead.pk}')

    first_name = (lead.full_name or '').split()[0] if lead.full_name else ''

    response = requests.post(
        f'{MAILGUN_API_URL}/{config["domain"]}/messages',
        auth=('api', api_key),
        data={
            'from': config['from'],
            'to': [lead.email],
            'subject': config['subject'],
            'template': config['template'],
            'h:X-Mailgun-Variables': f'{{"first_name": "{first_name}"}}',
        },
        timeout=15,
    )

    if response.status_code == 200:
        logger.info('[Mailgun] Lead %s: email sent to %s via %s', lead.pk, lead.email, config['domain'])
    else:
        logger.error(
            '[Mailgun] Lead %s: failed (%d) — %s',
            lead.pk, response.status_code, response.text[:500],
        )
        response.raise_for_status()
