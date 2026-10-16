"""
El alumno que ya tiene su llamada y choca con el límite de reservas.

Dos cosas estaban mal dentro del iframe de la academia:

  * la página de «máximo de reservas alcanzado» no se dejaba embeber, así que
    en lugar de la explicación el alumno veía el error del navegador de que la
    página había rechazado la conexión;
  * nada le avisaba antes: elegía día, rellenaba el formulario y solo al final
    se encontraba con el tope.

Ahora la página del límite se pinta dentro del iframe y, como con el token de la
academia ya se sabe quién es, la página de reserva le avisa nada más abrirla.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from calendario.bookings.models import Reserva
from tests.bookings.test_embed_lms import (
    EMAIL_ALUMNO, NOMBRE_ALUMNO, MOCKS_GCAL, ORIGEN_LMS, EmbedBase, token_lms,
)


def texto_fecha(d):
    return date_format(d, r'j \d\e F')


class LimiteBase(EmbedBase):

    def setUp(self):
        super().setUp()
        for et in (self.privado, self.publico):
            et.limite_reservas = 1
            et.limite_reservas_dias = 30
            et.save(update_fields=['limite_reservas', 'limite_reservas_dias'])
        self.tz = ZoneInfo(self.host.timezone)
        self.hoy = timezone.now().astimezone(self.tz).date()

    def reserva_alumno(self, dias, et=None):
        """Reserva confirmada del alumno a `dias` de hoy (negativo: en el pasado)."""
        et = et or self.privado
        inicio = timezone.now().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=dias)
        return Reserva.objects.create(
            event_type=et, host=self.host, inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=et.duracion_minutos),
            nombre_invitado=NOMBRE_ALUMNO, email_invitado=EMAIL_ALUMNO,
        )

    def pagina_alumno(self, et=None):
        return self.client.get(self.url_pagina(et or self.privado) + f'?t={token_lms()}')


class PaginaDelLimiteEnElIframeTest(LimiteBase):

    def url_limite(self, et):
        return reverse('public_token:limite_reservas') + f'?evento={et.pk}'

    def test_la_del_evento_de_la_academia_se_deja_embeber(self):
        resp = self.client.get(self.url_limite(self.privado))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('X-Frame-Options', resp)
        self.assertEqual(resp['Content-Security-Policy'], f'frame-ancestors {ORIGEN_LMS}')

    def test_la_de_un_evento_publico_sigue_sin_embeberse(self):
        resp = self.client.get(self.url_limite(self.publico))
        self.assertIn('X-Frame-Options', resp)

    def test_el_alumno_que_choca_con_el_tope_acaba_en_una_pagina_que_se_ve(self):
        """El recorrido entero: reserva desde el iframe, tope, página del tope."""
        self.reserva_alumno(dias=-5)
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(
                self.url_submit(self.privado) + f'?t={token_lms()}',
                self.datos_reserva(),
                follow=True,
            )
        self.assertTemplateUsed(resp, 'pages/public/booking/limite_reservas.html')
        self.assertNotIn('X-Frame-Options', resp)


class AvisoAntesDeElegirHoraTest(LimiteBase):

    def test_con_una_llamada_futura_avisa_y_dice_desde_cuando(self):
        reserva = self.reserva_alumno(dias=5)
        cita = reserva.inicio_utc.astimezone(self.tz).date()

        resp = self.pagina_alumno()
        aviso = resp.context['aviso_limite']
        self.assertEqual(aviso['cita'], texto_fecha(cita))
        self.assertTrue(aviso['cita_futura'])
        self.assertEqual(aviso['desde'], texto_fecha(cita + timedelta(days=30)))
        self.assertContains(resp, 'Ya tienes una llamada agendada para el')

    def test_con_la_casilla_de_uno_por_invitado_ofrece_cambiarla(self):
        self.reserva_alumno(dias=5)
        self.assertTrue(self.pagina_alumno().context['aviso_limite']['puede_cambiarla'])

        self.privado.unico_por_invitado = False
        self.privado.save(update_fields=['unico_por_invitado'])
        resp = self.pagina_alumno()
        self.assertFalse(resp.context['aviso_limite']['puede_cambiarla'])
        self.assertNotContains(resp, 'te preguntaremos antes de cambiarla')

    def test_con_una_llamada_pasada_dentro_de_la_ventana_tambien_avisa(self):
        reserva = self.reserva_alumno(dias=-10)
        cita = reserva.inicio_utc.astimezone(self.tz).date()

        aviso = self.pagina_alumno().context['aviso_limite']
        self.assertEqual(aviso['cita'], texto_fecha(cita))
        self.assertFalse(aviso['cita_futura'])
        self.assertFalse(aviso['puede_cambiarla'])
        self.assertEqual(aviso['desde'], texto_fecha(cita + timedelta(days=30)))

    def test_sin_llamadas_no_avisa(self):
        self.assertIsNone(self.pagina_alumno().context['aviso_limite'])

    def test_una_llamada_fuera_de_la_ventana_no_avisa(self):
        self.reserva_alumno(dias=-40)
        self.assertIsNone(self.pagina_alumno().context['aviso_limite'])

    def test_una_llamada_cancelada_no_cuenta(self):
        reserva = self.reserva_alumno(dias=5)
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.save(update_fields=['estado'])
        self.assertIsNone(self.pagina_alumno().context['aviso_limite'])

    def test_sin_limite_configurado_no_avisa(self):
        self.reserva_alumno(dias=5)
        self.privado.limite_reservas = None
        self.privado.limite_reservas_dias = None
        self.privado.save(update_fields=['limite_reservas', 'limite_reservas_dias'])
        self.assertIsNone(self.pagina_alumno().context['aviso_limite'])

    def test_sin_token_no_se_sabe_quien_es_y_no_avisa(self):
        """En la página pública la identidad llega con el formulario, no antes."""
        self.reserva_alumno(dias=5, et=self.publico)
        resp = self.client.get(self.url_pagina(self.publico))
        self.assertNotIn('aviso_limite', resp.context)
