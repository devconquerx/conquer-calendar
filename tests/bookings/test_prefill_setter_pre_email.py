"""
El pre_email del setter en los links que genera el CRM directo a `/e/<equipo>/`.

El CRM llama `setter_pre_email` a ese parámetro (así lo lee su propio ingest,
que resuelve el usuario con `resolve_setter_by_pre_email`); el funnel lo llama
`setter`. La página solo miraba `setter`, así que en un link como

    /e/<equipo>/?utm_medium=lead_register_without_preschedule&setter_pre_email=damian.lefosse

el dato se perdía en la primera pantalla: la Reserva se creaba sin setter y el
payload de IngestSchedule omitía `setter_pre_email` (push_schedule descarta los
None), de modo que el CRM no tenía a quién atribuir la llamada.
"""
from django.test import TestCase
from django.urls import reverse

from tests.factories import crear_disponibilidad, crear_event_type, crear_host


class PrefillSetterPreEmailTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.event_type = crear_event_type(self.host, nombre='Sesión de consultoría')
        self.event_type.slug_equipo = 'sesion-de-consultoria-eu'
        self.event_type.save(update_fields=['slug_equipo'])

    def url(self, query=''):
        base = reverse('public_team:booking_page', kwargs={'slug_equipo': 'sesion-de-consultoria-eu'})
        return base + query

    def test_el_nombre_del_crm_llega_al_hidden(self):
        resp = self.client.get(self.url('?setter_pre_email=damian.lefosse'))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['setter'], 'damian.lefosse')

    def test_el_nombre_del_funnel_sigue_funcionando(self):
        resp = self.client.get(self.url('?setter=damian.lefosse'))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['setter'], 'damian.lefosse')

    def test_si_vienen_los_dos_manda_setter(self):
        resp = self.client.get(self.url('?setter=del.funnel&setter_pre_email=del.crm'))

        self.assertEqual(resp.context['setter'], 'del.funnel')

    def test_sin_parametro_queda_vacio(self):
        resp = self.client.get(self.url())

        self.assertEqual(resp.context['setter'], '')
