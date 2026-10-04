"""El sweep reenvía a ActiveCampaign (puente de Relay) y al CRM sin esperar a nada.

La validación del email es cosa de Relay: aquí no hay veredicto que esperar ni
lead que frenar.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from calendario.leads.models import Lead
from calendario.leads.tasks import sweep_incomplete_leads

RUTA = 'calendario.leads.tasks.'


@override_settings(CRM_INGEST_ENABLED=True)
class SweepSinValidacionTest(TestCase):

    def _lead(self, **campos):
        with patch('celery.app.task.Task.apply_async'):
            lead = Lead.objects.create(email='ana@ejemplo.com', funnel='cb-eu', **campos)
        Lead.objects.filter(pk=lead.pk).update(created=timezone.now() - timedelta(minutes=30))
        return lead

    def _barrer(self):
        nombres = ('process_activecampaign', 'process_crm_send', 'process_supabase',
                   'process_respondio', 'process_funnelchat', 'process_meta_capi',
                   'process_tiktok_events', 'process_google_ads')
        parches = {n: patch(RUTA + n) for n in nombres}
        activos = {n: p.start() for n, p in parches.items()}
        try:
            sweep_incomplete_leads()
            return activos
        finally:
            for p in parches.values():
                p.stop()

    def test_reencola_ac_y_crm_directamente(self):
        lead = self._lead()
        activos = self._barrer()
        activos['process_activecampaign'].delay.assert_called_once_with(lead.pk)
        activos['process_crm_send'].delay.assert_called_once_with(lead.pk)

    def test_no_repite_lo_ya_hecho(self):
        lead = self._lead()
        lead.tags.add('activecampaign_done', 'crm_done')
        activos = self._barrer()
        activos['process_activecampaign'].delay.assert_not_called()
        activos['process_crm_send'].delay.assert_not_called()
