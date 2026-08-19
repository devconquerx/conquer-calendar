"""
Tests de la feature free/busy, calcada de Calendly:

- La regla es un match contra el TÍTULO. La app nunca escribe la palabra: una
  reserva nace "abierta" (`permite_overbooking=True`) solo si el título que le
  toca —el del formato del tipo de evento— ya contiene la palabra/emoji. En la
  práctica: la palabra va en el nombre del tipo de evento.
- Palabras configuradas pero título que no matchea → comportamiento normal, un
  slot = una reserva.
- Cuando el host le QUITA la palabra al evento en Google Calendar, el sync pone
  `permite_overbooking=False` y el slot se cierra.
- El horario también se cierra SOLO al llegar a MAX_RESERVAS_POR_SLOT (2, fijo),
  sin tocar Google Calendar. Solo cuentan las confirmadas: cancelar una vuelve a
  dejar hueco. Este tope es nuestro; Calendly no lo tiene.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase

from calendario.bookings.exceptions import SlotNoDisponibleError
from calendario.bookings.models import Reserva
from calendario.bookings.services import MAX_RESERVAS_POR_SLOT, cancelar_reserva
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
        # La palabra va en el NOMBRE del tipo de evento, como en Calendly: así el
        # título de cada evento creado la lleva y matchea la regla.
        self.et = crear_event_type(self.host, nombre=f'{PALABRA} Reunión test')
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
    def test_titulo_es_el_del_formato_sin_anadidos(self, _ev, _conf):
        r = _reservar(self.et, slot_futuro(), 'a@x.com')
        # La palabra sale del nombre del tipo de evento, no la mete la app.
        self.assertEqual(
            _titulo_evento(r),
            f'Lead y {r.host.nombre_display()} - {PALABRA} Reunión test',
        )

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_varias_reservas_en_el_mismo_slot(self, _ev, _conf):
        inicio = slot_futuro()
        _reservar(self.et, inicio, 'a@x.com')
        _reservar(self.et, inicio, 'b@x.com')
        n = Reserva.objects.filter(
            host=self.host, inicio_utc=inicio, estado=Reserva.Estado.CONFIRMADA,
        ).count()
        self.assertEqual(n, MAX_RESERVAS_POR_SLOT)

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
    def test_tope_son_dos(self, _ev, _conf):
        self.assertEqual(MAX_RESERVAS_POR_SLOT, 2)
        inicio = slot_futuro()
        _reservar(self.et, inicio, 'a@x.com')
        _reservar(self.et, inicio, 'b@x.com')
        # La tercera ya no entra: el horario se cerró solo, sin tocar GCal.
        with self.assertRaises(SlotNoDisponibleError):
            _reservar(self.et, inicio, 'c@x.com')

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_cancelar_una_libera_hueco(self, _ev, _conf):
        inicio = slot_futuro()
        primera = _reservar(self.et, inicio, 'a@x.com')
        _reservar(self.et, inicio, 'b@x.com')
        with self.assertRaises(SlotNoDisponibleError):
            _reservar(self.et, inicio, 'c@x.com')
        # Al cancelar una, solo quedan 1 activa -> vuelve a haber sitio.
        cancelar_reserva(primera)
        _reservar(self.et, inicio, 'c@x.com')
        activas = Reserva.objects.filter(
            host=self.host, inicio_utc=inicio, estado=Reserva.Estado.CONFIRMADA,
        ).count()
        self.assertEqual(activas, 2)
        # Y con el cupo lleno otra vez, la siguiente vuelve a rebotar.
        with self.assertRaises(SlotNoDisponibleError):
            _reservar(self.et, inicio, 'd@x.com')

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_el_tope_no_cierra_otros_horarios(self, _ev, _conf):
        # Llenar un horario no debe afectar a otro distinto del mismo día.
        inicio = slot_futuro()
        _reservar(self.et, inicio, 'a@x.com')
        _reservar(self.et, inicio, 'b@x.com')
        otro = inicio + timedelta(hours=1)
        r = _reservar(self.et, otro, 'c@x.com')
        self.assertEqual(r.inicio_utc, otro)

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


class PalabrasPeroTituloQueNoMatcheaTest(TestCase):
    """El tipo de evento tiene reglas, pero su nombre no lleva la palabra."""

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host, nombre='Reunión test')
        self.et.gcal_palabras_ignorar = PALABRA
        self.et.save(update_fields=['gcal_palabras_ignorar'])
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_la_app_no_mete_la_palabra_en_el_titulo(self, _ev, _conf):
        r = _reservar(self.et, slot_futuro(), 'a@x.com')
        self.assertNotIn(PALABRA, _titulo_evento(r))

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_reserva_nace_cerrada(self, _ev, _conf):
        r = _reservar(self.et, slot_futuro(), 'a@x.com')
        self.assertFalse(r.permite_overbooking)

    @patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
    @patch('calendario.bookings.services.crear_evento_google')
    def test_no_admite_doble_booking(self, _ev, _conf):
        inicio = slot_futuro()
        _reservar(self.et, inicio, 'a@x.com')
        with self.assertRaises(SlotNoDisponibleError):
            _reservar(self.et, inicio, 'b@x.com')


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
