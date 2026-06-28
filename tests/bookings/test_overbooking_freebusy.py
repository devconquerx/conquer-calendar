"""
Tests de la feature free/busy estilo Calendly (Opción A):

- Un tipo de evento con palabras configuradas (`gcal_palabras_ignorar`) crea
  reservas "abiertas" (`permite_overbooking=True`): el título del evento nace con
  la palabra/emoji y se puede reservar encima (varias reservas en el mismo slot).
- Cuando el host le QUITA la palabra al evento en Google Calendar, el sync pone
  `permite_overbooking=False` y el slot se cierra (deja de admitir reservas).
- Sin palabras configuradas, el comportamiento es el de siempre (un slot = una
  reserva).
"""
from unittest.mock import patch

from django.test import TestCase

from calendario.bookings.exceptions import SlotNoDisponibleError
from calendario.bookings.models import Reserva
from calendario.bookings.services import crear_reserva as svc_crear
from calendario.google_calendar.services import _titulo_evento
from calendario.google_calendar.sync import _reconciliar_overbooking
from tests.factories import (
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)

PALABRA = '🔓'


def _reservar(et, inicio, email):
    return svc_crear(
        event_type=et, inicio_utc=inicio,
        nombre_invitado='Lead', email_invitado=email,
    )


class OverbookingFreeBusyTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        self.et.gcal_palabras_ignorar = PALABRA
        self.et.save(update_fields=['gcal_palabras_ignorar'])
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_reserva_nace_abierta(self, _ev, _conf):
        r = _reservar(self.et, slot_futuro(), 'a@x.com')
        self.assertTrue(r.permite_overbooking)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_titulo_incluye_la_palabra(self, _ev, _conf):
        r = _reservar(self.et, slot_futuro(), 'a@x.com')
        self.assertIn(PALABRA, _titulo_evento(r))

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_varias_reservas_en_el_mismo_slot(self, _ev, _conf):
        inicio = slot_futuro()
        _reservar(self.et, inicio, 'a@x.com')
        _reservar(self.et, inicio, 'b@x.com')
        _reservar(self.et, inicio, 'c@x.com')
        n = Reserva.objects.filter(
            host=self.host, inicio_utc=inicio, estado=Reserva.Estado.CONFIRMADA,
        ).count()
        self.assertEqual(n, 3)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_quitar_la_palabra_cierra_el_slot(self, _ev, _conf):
        inicio = slot_futuro()
        ganadora = _reservar(self.et, inicio, 'a@x.com')
        _reservar(self.et, inicio, 'b@x.com')
        # El host le quita la palabra a la ganadora en Google Calendar → cierra.
        ganadora.permite_overbooking = False
        ganadora.save(update_fields=['permite_overbooking'])
        with self.assertRaises(SlotNoDisponibleError):
            _reservar(self.et, inicio, 'c@x.com')

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_reconciliar_quita_flag_al_quitar_palabra(self, _ev, _conf):
        r = _reservar(self.et, slot_futuro(), 'a@x.com')
        r.google_event_id = 'gcal-evt-1'
        r.save(update_fields=['google_event_id'])
        # Título SIN la palabra → el reconcile cierra (permite_overbooking=False).
        _reconciliar_overbooking(self.host, {'gcal-evt-1': 'Reunión con Lead'})
        r.refresh_from_db()
        self.assertFalse(r.permite_overbooking)
        # Vuelve a aparecer la palabra → reabre.
        _reconciliar_overbooking(self.host, {'gcal-evt-1': f'{PALABRA} Reunión con Lead'})
        r.refresh_from_db()
        self.assertTrue(r.permite_overbooking)


class SinPalabrasComportamientoNormalTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)  # sin gcal_palabras_ignorar
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_reserva_normal_no_abre_overbooking(self, _ev, _conf):
        r = _reservar(self.et, slot_futuro(), 'a@x.com')
        self.assertFalse(r.permite_overbooking)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_slot_se_ocupa_con_una_reserva(self, _ev, _conf):
        inicio = slot_futuro()
        _reservar(self.et, inicio, 'a@x.com')
        with self.assertRaises(SlotNoDisponibleError):
            _reservar(self.et, inicio, 'b@x.com')

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_titulo_sin_palabra(self, _ev, _conf):
        r = _reservar(self.et, slot_futuro(), 'a@x.com')
        self.assertNotIn(PALABRA, _titulo_evento(r))
