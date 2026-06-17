import logging

import requests
from django.conf import settings

from .utils import get_school_code, get_region_from_lead

logger = logging.getLogger(__name__)

# ActiveCampaign custom field IDs for UTM/click params
CUSTOM_FIELD_MAP = {
    'utm_source': '43',
    'utm_campaign': '42',
    'utm_medium': '44',
    'utm_content': '46',
    'utm_term': '45',
    'gclid': '41',
    'fbclid': '68',
}

# Tag por funnel (school-region). El valor puede ser un ID numérico de
# ActiveCampaign o el NOMBRE del tag (se resuelve a ID por nombre en runtime,
# igual que conquer-crm). Conquer Legal (cg) usa el nombre porque su tag se
# gestiona por nombre en AC.
FUNNEL_TAG_MAP = {
    'cb-latam': '449', 'cb-eu': '451', 'cb-us': '452', 'cb-ge': '459',
    'fi-latam': '454', 'fi-eu': '456', 'fi-us': '457',
    'cf-latam': '454', 'cf-eu': '456', 'cf-us': '457',
    'cl-latam': '465', 'cl-eu': '466', 'cl-us': '468',
    'cg-latam': 'cg-latam', 'cg-eu': 'cg-eu', 'cg-us': 'cg-us',
}

# IDs numéricos conocidos (para quitar tags de escuela previos antes de añadir
# el nuevo). Los valores por nombre se resuelven aparte en push_lead.
ALL_SCHOOL_TAG_IDS = {tag for tag in FUNNEL_TAG_MAP.values() if str(tag).isdigit()}

# List IDs per school
SCHOOL_LIST_MAP = {
    'cb': '19',
    'fi': '32',
    'cf': '32',
    'cl': '33',
}


class ActiveCampaignClient:
    def __init__(self):
        url = getattr(settings, 'ACTIVECAMPAIGN_API_URL', '')
        self.api_key = getattr(settings, 'ACTIVECAMPAIGN_API_KEY', '')
        self.base_url = url.rstrip('/').removesuffix('/api/3').removesuffix('/api/3/')
        self.base_url = f'{self.base_url}/api/3'

    @property
    def headers(self):
        return {'Api-Token': self.api_key, 'Content-Type': 'application/json'}

    def _get(self, path, params=None):
        return requests.get(f'{self.base_url}{path}', headers=self.headers, params=params, timeout=10)

    def _post(self, path, json=None):
        return requests.post(f'{self.base_url}{path}', headers=self.headers, json=json, timeout=10)

    def _delete(self, path):
        return requests.delete(f'{self.base_url}{path}', headers=self.headers, timeout=10)

    def create_or_update_contact(self, email, first_name=None, field_values=None):
        """Create or update a contact. Returns contact dict or None."""
        contact = {'email': email}
        if first_name:
            contact['firstName'] = first_name
        if field_values:
            contact['fieldValues'] = [{'field': k, 'value': v} for k, v in field_values.items() if v]

        resp = self._post('/contact/sync', json={'contact': contact})
        if resp.status_code == (200 or 201):
            return resp.json().get('contact')
        resp = self._post('/contacts', json={'contact': contact})
        if resp.status_code in (200, 201):
            return resp.json().get('contact')
        return None

    def get_contact_tags(self, contact_id):
        """Get all tags for a contact. Returns list of contactTag dicts."""
        resp = self._get(f'/contacts/{contact_id}/contactTags')
        if resp.status_code == 200:
            return resp.json().get('contactTags', [])
        return []

    def get_tag_by_name(self, name):
        """Find an exact tag by name. Returns the tag dict or None."""
        if not name:
            return None
        resp = self._get('/tags', params={'search': str(name).strip()})
        if resp.status_code != 200:
            return None
        normalized = str(name).strip().lower()
        for tag in resp.json().get('tags', []):
            if str(tag.get('tag') or '').strip().lower() == normalized:
                return tag
        return None

    def add_tag(self, contact_id, tag_id):
        """Add a tag to a contact."""
        self._post('/contactTags', json={'contactTag': {'contact': str(contact_id), 'tag': str(tag_id)}})

    def remove_tag(self, contact_tag_id):
        """Remove a tag from a contact (by contactTag ID, not tag ID)."""
        self._delete(f'/contactTags/{contact_tag_id}')

    def add_to_list(self, contact_id, list_id, status=1):
        """Add contact to a list. status=1 Active, status=2 Unsubscribed."""
        self._post('/contactLists', json={
            'contactList': {'list': str(list_id), 'contact': str(contact_id), 'status': status}
        })


def _resolve_tag_id(client, tag_value):
    """Resuelve un valor de FUNNEL_TAG_MAP a un ID numérico de tag de AC.

    Si el valor ya es numérico se usa tal cual; si es un nombre (p. ej.
    'cg-eu') se busca por nombre en ActiveCampaign. Devuelve None si no se
    encuentra. Espeja el patrón de conquer-crm.
    """
    value = str(tag_value or '').strip()
    if not value:
        return None
    if value.isdigit():
        return value
    tag = client.get_tag_by_name(value)
    tag_id = str((tag or {}).get('id') or '').strip()
    return tag_id or None


def push_lead(lead):
    """Sync lead to ActiveCampaign: create/update contact, set tags, add to list."""
    api_url = getattr(settings, 'ACTIVECAMPAIGN_API_URL', '')
    api_key = getattr(settings, 'ACTIVECAMPAIGN_API_KEY', '')
    if not api_url or not api_key:
        logger.warning('[ActiveCampaign] API not configured')
        return

    if not lead.email:
        return

    school_code = get_school_code(lead)
    region = get_region_from_lead(lead).lower()  # 'latam', 'eu', 'usa'
    region_key = 'us' if region == 'usa' else region
    funnel_key = f'{school_code}-{region_key}' if school_code else None

    client = ActiveCampaignClient()

    try:
        field_values = {}
        for lead_field, ac_field_id in CUSTOM_FIELD_MAP.items():
            val = getattr(lead, lead_field, None)
            if val:
                field_values[ac_field_id] = str(val)

        first_name = lead.full_name.split()[0] if lead.full_name else None

        contact = client.create_or_update_contact(lead.email, first_name, field_values)
        if not contact:
            logger.warning(f'[ActiveCampaign] Lead {lead.pk}: failed to create/update contact')
            return

        contact_id = contact.get('id')
        if not contact_id:
            return

        if funnel_key and funnel_key in FUNNEL_TAG_MAP:
            target_tag_id = _resolve_tag_id(client, FUNNEL_TAG_MAP[funnel_key])
            if target_tag_id:
                tags_to_clear = ALL_SCHOOL_TAG_IDS | {str(target_tag_id)}
                existing_tags = client.get_contact_tags(contact_id)
                for ct in existing_tags:
                    if str(ct.get('tag')) in tags_to_clear:
                        client.remove_tag(ct.get('id'))

                client.add_tag(contact_id, target_tag_id)
            else:
                logger.warning(
                    f'[ActiveCampaign] Lead {lead.pk}: no se pudo resolver el tag '
                    f'para funnel "{funnel_key}" (valor={FUNNEL_TAG_MAP[funnel_key]!r})'
                )

        list_id = SCHOOL_LIST_MAP.get(school_code)
        if list_id:
            client.add_to_list(contact_id, list_id, status=1)

        logger.info(f'[ActiveCampaign] Lead {lead.pk} synced, contact_id={contact_id}')

    except Exception as e:
        logger.error(f'[ActiveCampaign] Lead {lead.pk} error: {e}')
        raise
    finally:
        try:
            lead.is_form_vsl_processed = True
            lead.save(update_fields=['is_form_vsl_processed'])
        except Exception as save_err:
            logger.error(f'[ActiveCampaign] Lead {lead.pk} failed to save is_form_vsl_processed: {save_err}')
