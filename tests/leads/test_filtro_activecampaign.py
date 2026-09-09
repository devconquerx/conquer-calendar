"""
A quién dejamos entrar en ActiveCampaign.

Meter una dirección inexistente en AC es un rebote duro asegurado, y el rebote
duro no puede pasar del 2% sin que la reputación de la IP de envío se resienta.
Por eso ActiveCampaign ya no sale en paralelo con la validación, sino después:
`process_neverbounce` decide con el veredicto delante.

La regla es asimétrica a propósito. Solo se frena el lead cuando el servidor de
correo ha dicho por escrito que ese buzón no existe. Cualquier otra cosa —un
dominio catch-all, un timeout, un proveedor que no nos habla, o directamente no
haber podido comprobarlo— deja pasar el lead: un lead bueno bloqueado cuesta
mucho más que uno malo colado.
"""
from unittest.mock import patch

from django.test import TestCase

from calendario.leads.models import Lead
from calendario.leads.tasks import process_neverbounce


class FiltroActiveCampaignTest(TestCase):
    """Qué hace process_neverbounce con AC según el veredicto del email."""

    def _correr(self, neverbounce_result):
        """Corre la tarea con el veredicto ya puesto y devuelve (lead, mock_AC)."""
        lead = Lead.objects.create(email='alguien@ejemplo.com',
                                   neverbounce_result=neverbounce_result)
        with patch('calendario.leads.tasks.process_activecampaign.delay') as ac, \
             patch('calendario.leads.tasks.process_crm_send.delay'):
            process_neverbounce(lead.pk)
        lead.refresh_from_db()
        return lead, ac

    def test_buzon_inexistente_no_entra_en_activecampaign(self):
        lead, ac = self._correr({
            'result': 'invalid', 'is_rejected': True,
            'source': 'own_smtp', 'reason': 'smtp_user_unknown',
        })

        ac.assert_not_called()
        self.assertIn('activecampaign_skipped', {t.name for t in lead.tags.all()})

    def test_email_valido_entra(self):
        lead, ac = self._correr({
            'result': 'valid', 'is_rejected': False, 'source': 'own_smtp',
        })

        ac.assert_called_once_with(lead.pk)
        self.assertNotIn('activecampaign_skipped', {t.name for t in lead.tags.all()})

    def test_catchall_entra(self):
        """Yahoo acepta cualquier dirección: su 250 no prueba que el buzón exista,
        pero tampoco que no exista. En la duda, se envía."""
        _lead, ac = self._correr({
            'result': 'catchall', 'is_rejected': False, 'source': 'own_smtp',
        })

        ac.assert_called_once()

    def test_no_concluyente_entra(self):
        """Outlook no nos deja sondear. No sabemos nada del buzón, así que pasa."""
        _lead, ac = self._correr({
            'result': 'unknown', 'is_rejected': False,
            'source': 'own_smtp', 'reason': 'smtp_unreachable',
        })

        ac.assert_called_once()

    def test_sin_veredicto_entra(self):
        """Si la validación no llegó a producir nada, el lead no se queda atrapado."""
        lead = Lead.objects.create(email='alguien@ejemplo.com')
        with patch('calendario.leads.services.email_validation.validate_email'), \
             patch('calendario.leads.tasks.process_activecampaign.delay') as ac, \
             patch('calendario.leads.tasks.process_crm_send.delay'):
            process_neverbounce(lead.pk)

        ac.assert_called_once_with(lead.pk)

    def test_el_crm_recibe_el_lead_aunque_el_email_sea_malo(self):
        """Filtrar es cosa de ActiveCampaign: al CRM va todo, con su veredicto."""
        lead = Lead.objects.create(email='alguien@ejemplo.com', neverbounce_result={
            'result': 'invalid', 'is_rejected': True, 'source': 'own_smtp',
        })
        with patch('calendario.leads.tasks.process_activecampaign.delay'), \
             patch('calendario.leads.tasks.process_crm_send.delay') as crm:
            process_neverbounce(lead.pk)

        crm.assert_called_once_with(lead.pk)
