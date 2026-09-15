"""
Bloqueo de invitados desde el admin.

Se bloquea un email concreto (el resto de su proveedor sigue reservando) o un
dominio entero. Quien está bloqueado no crea la reserva y sale redirigido a la
URL global de `ConfigBloqueos`, o a la página propia si no hay ninguna.
"""
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from calendario.bookings.bloqueos import buscar_bloqueo
from calendario.bookings.exceptions import InvitadoBloqueadoError
from calendario.bookings.models import BloqueoInvitado, ConfigBloqueos, Reserva
from calendario.bookings.services import crear_reserva, reemplazar_reserva
from tests.factories import (
    NOMBRE_INVITADO, crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)

EMAIL = BloqueoInvitado.Tipo.EMAIL
DOMINIO = BloqueoInvitado.Tipo.DOMINIO


def bloquear(tipo, valor, **extra):
    return BloqueoInvitado.objects.create(tipo=tipo, valor=valor, **extra)


class CoincidenciaTest(TestCase):

    def test_email_concreto_no_se_lleva_al_resto_del_proveedor(self):
        bloquear(EMAIL, 'pepito@gmail.com')
        self.assertIsNotNone(buscar_bloqueo('pepito@gmail.com'))
        self.assertIsNotNone(buscar_bloqueo('  PEPITO@Gmail.com '))
        self.assertIsNone(buscar_bloqueo('juanito@gmail.com'))

    def test_email_no_se_salta_con_alias_ni_puntos_de_gmail(self):
        bloquear(EMAIL, 'pepito@gmail.com')
        self.assertIsNotNone(buscar_bloqueo('pepito+otra@gmail.com'))
        self.assertIsNotNone(buscar_bloqueo('pe.pi.to@gmail.com'))

    def test_los_puntos_solo_se_ignoran_en_gmail(self):
        bloquear(EMAIL, 'pepito@empresa.com')
        self.assertIsNone(buscar_bloqueo('pe.pito@empresa.com'))

    def test_dominio_con_extension_incluye_subdominios(self):
        bloquear(DOMINIO, 'somoshackers.com')
        self.assertIsNotNone(buscar_bloqueo('loco@somoshackers.com'))
        self.assertIsNotNone(buscar_bloqueo('loco@mail.somoshackers.com'))
        self.assertIsNone(buscar_bloqueo('loco@nosomoshackers.com'))
        self.assertIsNone(buscar_bloqueo('loco@somoshackers.net'))

    def test_dominio_sin_extension_bloquea_cualquier_terminacion(self):
        bloquear(DOMINIO, '@somoshackers')
        for email in ('a@somoshackers.com', 'a@somoshackers.net',
                      'a@somoshackers.co.uk', 'a@mail.somoshackers.es'):
            self.assertIsNotNone(buscar_bloqueo(email), email)
        self.assertIsNone(buscar_bloqueo('a@nosomoshackers.com'))
        self.assertIsNone(buscar_bloqueo('a@gmail.com'))

    def test_un_dominio_sin_extension_no_casa_con_la_terminacion(self):
        bloquear(DOMINIO, 'com')
        self.assertIsNone(buscar_bloqueo('a@gmail.com'))

    def test_la_arroba_del_dominio_se_quita_al_guardar(self):
        self.assertEqual(bloquear(DOMINIO, ' @SomosHackers.com ').valor, 'somoshackers.com')

    def test_un_bloqueo_inactivo_no_bloquea(self):
        bloquear(EMAIL, 'pepito@gmail.com', activo=False)
        self.assertIsNone(buscar_bloqueo('pepito@gmail.com'))

    def test_validacion_del_admin(self):
        with self.assertRaises(ValidationError):
            BloqueoInvitado(tipo=EMAIL, valor='esto-no-es-un-email').full_clean()
        with self.assertRaises(ValidationError):
            BloqueoInvitado(tipo=DOMINIO, valor='pepito@gmail.com').full_clean()
        BloqueoInvitado(tipo=DOMINIO, valor='@somoshackers').full_clean()


@patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
@patch('calendario.bookings.services.crear_evento_google')
class ServicioTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

    def _reservar(self, email, inicio=None):
        return crear_reserva(
            event_type=self.et, inicio_utc=inicio or slot_futuro(),
            nombre_invitado=NOMBRE_INVITADO, email_invitado=email,
        )

    def test_bloqueado_no_crea_la_reserva(self, *_):
        bloquear(DOMINIO, 'somoshackers')
        with self.assertRaises(InvitadoBloqueadoError):
            self._reservar('loco@somoshackers.com')
        self.assertFalse(Reserva.objects.exists())

    def test_reagendar_bloqueado_no_cancela_la_reserva_vieja(self, *_):
        vieja = self._reservar('pepito@gmail.com')
        bloquear(EMAIL, 'pepito@gmail.com')
        with self.assertRaises(InvitadoBloqueadoError):
            reemplazar_reserva(
                reserva_vieja_pk=vieja.pk, event_type=self.et,
                inicio_utc=slot_futuro(hora=12),
                nombre_invitado=NOMBRE_INVITADO, email_invitado='pepito@gmail.com',
            )
        vieja.refresh_from_db()
        self.assertEqual(vieja.estado, Reserva.Estado.CONFIRMADA)
        self.assertEqual(Reserva.objects.count(), 1)


@patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
@patch('calendario.bookings.services.crear_evento_google')
class VistaPublicaTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.url = reverse('public_booking:booking_submit', kwargs={
            'user_slug': self.host.slug, 'event_type_slug': self.et.slug,
        })

    def _post(self, email):
        return self.client.post(self.url, {
            'inicio_utc': slot_futuro().isoformat(),
            'nombre_invitado': NOMBRE_INVITADO,
            'email_invitado': email,
            'telefono_invitado': '+34 600123456',
        })

    def test_sin_url_configurada_va_a_la_pagina_propia(self, *_):
        bloqueo = bloquear(EMAIL, 'pepito@gmail.com')
        resp = self._post('pepito@gmail.com')

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.endswith(reverse('public_token:reserva_no_procesada')))
        self.assertFalse(Reserva.objects.exists())
        bloqueo.refresh_from_db()
        self.assertEqual(bloqueo.intentos, 1)
        self.assertIsNotNone(bloqueo.ultimo_intento)

    def test_con_url_configurada_va_a_esa(self, *_):
        ConfigBloqueos.objects.create(url_redireccion='https://otra-pagina.com/lo-sentimos')
        bloquear(DOMINIO, 'somoshackers')
        resp = self._post('loco@somoshackers.com')
        self.assertRedirects(resp, 'https://otra-pagina.com/lo-sentimos', fetch_redirect_response=False)

    @patch('calendario.bookings.views_public._enviar_correos_confirmacion')
    def test_el_resto_del_proveedor_reserva_normal(self, *_):
        bloquear(EMAIL, 'pepito@gmail.com')
        resp = self._post('juanito@gmail.com')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Reserva.objects.count(), 1)

    def test_la_pagina_propia_se_muestra(self, *_):
        resp = self.client.get(reverse('public_token:reserva_no_procesada'))
        self.assertContains(resp, 'Lo sentimos, tu reserva no pudo ser procesada')
