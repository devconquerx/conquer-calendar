"""
Bloqueo de invitados desde el admin.

Se bloquea un email concreto (el resto de su proveedor sigue reservando) o un
dominio entero. Quien está bloqueado no crea la reserva y sale redirigido a la
URL global de `ConfigBloqueos`, o a la página propia si no hay ninguna.
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from calendario.bookings.bloqueos import buscar_bloqueo
from calendario.bookings.models import BloqueoInvitado

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
