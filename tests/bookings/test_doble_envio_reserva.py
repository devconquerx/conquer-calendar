"""
Un click, una reserva: el reenvío del mismo hueco no crea un registro nuevo.

El POST de reserva tarda un par de segundos en contestar (crea el evento de
Google y manda los correos antes de responder), así que es normal que la persona
vuelva a pulsar. Ese segundo envío llegaba a un servidor que ya tenía la reserva
hecha y, según el tipo de evento, o creaba una segunda reserva viva o sacaba el
modal de duplicado contra la propia persona que acababa de reservar — y aceptar
ese cartel cancelaba la reserva buena para crear otra con OTRO host, que es la
cita "doble" que reportaban los profesores.

Ahora `crear_reserva` es idempotente para (tipo, hueco, email).
"""
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from calendario.bookings.models import Reserva
from calendario.bookings.services import crear_reserva
from tests.factories import (
    EMAIL_INVITADO, NOMBRE_INVITADO,
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)


@patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
@patch('calendario.bookings.services.crear_evento_google')
class DobleEnvioServicioTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    TELEFONO = '+34 600123456'

    def _reservar(self, inicio, email=EMAIL_INVITADO, telefono=TELEFONO):
        return crear_reserva(
            event_type=self.et, inicio_utc=inicio,
            nombre_invitado=NOMBRE_INVITADO, email_invitado=email,
            telefono_invitado=telefono,
        )

    def test_el_segundo_envio_devuelve_la_misma_reserva(self, *_):
        inicio = slot_futuro()
        primera = self._reservar(inicio)
        segunda = self._reservar(inicio)

        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(Reserva.objects.filter(estado=Reserva.Estado.CONFIRMADA).count(), 1)

    def test_la_reserva_dice_si_es_nueva_o_reaprovechada(self, *_):
        inicio = slot_futuro()
        self.assertIs(self._reservar(inicio).reutilizada, False)
        self.assertIs(self._reservar(inicio).reutilizada, True)

    def test_tambien_protege_sin_la_casilla_de_reserva_unica(self, *_):
        # Es el caso que dejaba dos registros vivos de verdad: sin
        # `unico_por_invitado` no había ninguna comprobación.
        self.et.unico_por_invitado = False
        self.et.save(update_fields=['unico_por_invitado'])

        inicio = slot_futuro()
        primera = self._reservar(inicio)
        segunda = self._reservar(inicio)

        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(Reserva.objects.filter(estado=Reserva.Estado.CONFIRMADA).count(), 1)

    def test_el_email_no_distingue_mayusculas_ni_espacios(self, *_):
        inicio = slot_futuro()
        primera = self._reservar(inicio)
        segunda = self._reservar(inicio, email=f'  {EMAIL_INVITADO.upper()} ')
        self.assertEqual(primera.pk, segunda.pk)

    def test_otra_hora_del_mismo_dia_si_es_una_reserva_nueva(self, *_):
        self.et.unico_por_invitado = False
        self.et.save(update_fields=['unico_por_invitado'])

        primera = self._reservar(slot_futuro())
        otra = self._reservar(slot_futuro(hora=11))

        self.assertNotEqual(primera.pk, otra.pk)
        self.assertEqual(Reserva.objects.filter(estado=Reserva.Estado.CONFIRMADA).count(), 2)

    def test_otra_persona_en_el_mismo_hueco_no_se_confunde_con_un_reenvio(self, *_):
        self.et.unico_por_invitado = False
        self.et.save(update_fields=['unico_por_invitado'])
        otro_host = crear_host(email='segundo.host@conquerx.com')
        for dia in range(5):
            crear_disponibilidad(otro_host, dia=dia)
        from calendario.event_types.models import EventTypeXHost
        EventTypeXHost.objects.get_or_create(event_type=self.et, host=otro_host)

        inicio = slot_futuro()
        primera = self._reservar(inicio)
        ajena = self._reservar(inicio, email='otra.persona@ejemplo.com',
                               telefono='+34 611998877')

        self.assertNotEqual(primera.pk, ajena.pk)

    def test_el_mismo_telefono_con_otro_email_tambien_es_un_reenvio(self, *_):
        # Misma regla que el aviso de duplicado de siempre: mismo email O mismo
        # teléfono es la misma persona. Quien comparta teléfono con otro alumno
        # tiene que poner el suyo.
        self.et.unico_por_invitado = False
        self.et.save(update_fields=['unico_por_invitado'])

        inicio = slot_futuro()
        primera = self._reservar(inicio)
        segunda = self._reservar(inicio, email='otro.correo@ejemplo.com')

        self.assertEqual(primera.pk, segunda.pk)

    def test_una_reserva_cancelada_no_cuenta_como_reenvio(self, *_):
        inicio = slot_futuro()
        primera = self._reservar(inicio)
        primera.estado = Reserva.Estado.CANCELADA
        primera.save(update_fields=['estado'])

        segunda = self._reservar(inicio)
        self.assertNotEqual(primera.pk, segunda.pk)


@patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
@patch('calendario.bookings.services.crear_evento_google')
class DobleEnvioVistaPublicaTest(TestCase):
    """El doble POST de verdad, tal y como lo manda el navegador."""

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.url = reverse('public_booking:booking_submit', kwargs={
            'user_slug': self.host.slug, 'event_type_slug': self.et.slug,
        })

    def _post(self, inicio):
        return self.client.post(self.url, {
            'inicio_utc': inicio.isoformat(),
            'nombre_invitado': NOMBRE_INVITADO,
            'email_invitado': EMAIL_INVITADO,
            'telefono_invitado': '+34 600123456',
        })

    @patch('calendario.bookings.views_public._enviar_correos_confirmacion')
    def test_el_segundo_post_lleva_a_la_confirmacion_y_no_al_modal(self, mock_correos, *_):
        inicio = slot_futuro()

        primera = self._post(inicio)
        self.assertEqual(primera.status_code, 302)

        segunda = self._post(inicio)
        # 302 a la confirmación de la MISMA reserva. Antes esto era un 200 con
        # el cartel de "ya tienes una reserva".
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(primera.url, segunda.url)

        self.assertEqual(Reserva.objects.filter(estado=Reserva.Estado.CONFIRMADA).count(), 1)

    @patch('calendario.bookings.views_public._enviar_correos_confirmacion')
    def test_los_correos_de_confirmacion_salen_una_sola_vez(self, mock_correos, *_):
        inicio = slot_futuro()
        # Los correos se programan con `transaction.on_commit`, que dentro de un
        # TestCase no llega a dispararse solo: hay que capturar los callbacks.
        for _intento in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                self._post(inicio)

        self.assertEqual(mock_correos.call_count, 1)

    def test_el_boton_de_enviar_se_bloquea_tras_el_primer_click(self, *_):
        resp = self.client.get(reverse('public_booking:booking_page', kwargs={
            'user_slug': self.host.slug, 'event_type_slug': self.et.slug,
        }))
        html = resp.content.decode()
        self.assertIn('data-texto-enviando="Reservando…"', html)
        self.assertIn("btn.dataset.bloqueado === '1'", html)
