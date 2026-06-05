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

# Tag IDs per funnel (school-region)
FUNNEL_TAG_MAP = {
    'cb-latam': '449', 'cb-eu': '451', 'cb-us': '452', 'cb-ge': '459',
    'fi-latam': '454', 'fi-eu': '456', 'fi-us': '457',
    'cf-latam': '454', 'cf-eu': '456', 'cf-us': '457',
    'cl-latam': '465', 'cl-eu': '466', 'cl-us': '468',
}

# All school tag IDs (to remove old ones before adding new)
ALL_SCHOOL_TAGS = set(FUNNEL_TAG_MAP.values())

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
            existing_tags = client.get_contact_tags(contact_id)
            for ct in existing_tags:
                tag_id = ct.get('tag')
                if tag_id in ALL_SCHOOL_TAGS:
                    client.remove_tag(ct.get('id'))

            client.add_tag(contact_id, FUNNEL_TAG_MAP[funnel_key])

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
