"""
Reagendar desde el enlace de los correos (/r/<token>/reagendar/).

El botón «Reagendar» llevaba a la página pública del evento. En un evento «solo
alumnos» esa página pide el token del LMS, así que el alumno que llegaba desde
el correo se encontraba con «Esta página se abre desde la academia» y no podía
mover su clase.

Ahora el botón abre el calendario con el token de la reserva, que ya demuestra
que quien está delante es el invitado. La identidad sale de la reserva y, al
elegir hueco, se enseña el modal de «ya tienes una reserva» antes de cancelar
la actual: elegir hora no reagenda, lo hace aceptar el modal.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from calendario.bookings.correos import _build_vars
from calendario.bookings.models import Reserva
from calendario.event_types.models import EventType
from tests.factories import (
    EMAIL_INVITADO, NOMBRE_INVITADO,
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)

# Sin los mocks, crear_reserva sale a Google Calendar de verdad.
MOCKS_GCAL = [
    patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False),
    patch('calendario.bookings.services.crear_evento_google'),
    patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[]),
]


def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')


class ReagendarBase(TestCase):

    def setUp(self):
        self.client = Client()
        self.host = crear_host()
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.et = crear_event_type(self.host, nombre='Tutoría de alumnos')
        self.et.acceso = EventType.ACCESO_ACADEMIA
        self.et.save(update_fields=['acceso'])

        inicio = slot_futuro(dias=2, hora=11)
        self.reserva = Reserva.objects.create(
            event_type=self.et,
            host=self.host,
            inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=self.et.duracion_minutos),
            nombre_invitado=NOMBRE_INVITADO,
            email_invitado=EMAIL_INVITADO,
            telefono_invitado='+34 600123456',
            timezone_invitado='Europe/Madrid',
        )
        token = self.reserva.confirmacion_token
        self.url_pagina = reverse('public_token:reagendar_publica', kwargs={'token': token})
        self.url_submit = reverse('public_token:reagendar_submit', kwargs={'token': token})
        self.url_slots = reverse('public_token:reagendar_slots', kwargs={'token': token})

    def datos(self, **extra):
        datos = {
            'inicio_utc': iso(slot_futuro(dias=4, hora=12)),
            'telefono_invitado': '+34 600123456',
            'tz': 'Europe/Madrid',
        }
        datos.update(extra)
        return datos


class EnlaceDelCorreoTest(ReagendarBase):

    def test_el_correo_apunta_al_reagendar_de_la_reserva(self):
        vars_dict = _build_vars(self.reserva, 'https://calendar.example.com')
        self.assertEqual(
            vars_dict['link_reagendar'],
            f'https://calendar.example.com/r/{self.reserva.confirmacion_token}/reagendar/',
        )


class PaginaReagendarTest(ReagendarBase):

    def test_un_evento_solo_alumnos_se_abre_sin_token_del_lms(self):
        """Es el caso que estaba roto: la página pública lo mandaba a la academia."""
        resp = self.client.get(self.url_pagina)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'pages/public/booking/page.html')

    def test_la_disponibilidad_tambien_se_ve_sin_token(self):
        resp = self.client.get(self.url_slots)
        self.assertEqual(resp.status_code, 200)

    def test_la_identidad_sale_de_la_reserva_y_va_bloqueada(self):
        resp = self.client.get(self.url_pagina)
        self.assertEqual(resp.context['nombre_invitado'], NOMBRE_INVITADO)
        self.assertEqual(resp.context['email_invitado'], EMAIL_INVITADO)
        self.assertTrue(resp.context['campos_identidad_bloqueados'])
        self.assertEqual(resp.context['form_action_url'], self.url_submit)
        self.assertEqual(resp.context['slots_url'], self.url_slots)

    def test_una_reserva_cancelada_no_se_reagenda(self):
        self.reserva.estado = Reserva.Estado.CANCELADA
        self.reserva.save(update_fields=['estado'])
        confirmacion = reverse('public_token:confirmacion',
                               kwargs={'token': self.reserva.confirmacion_token})
        self.assertRedirects(self.client.get(self.url_pagina), confirmacion,
                             fetch_redirect_response=False)
        self.assertRedirects(self.client.post(self.url_submit, self.datos()), confirmacion,
                             fetch_redirect_response=False)
        self.assertEqual(self.client.get(self.url_slots).status_code, 410)


class ElegirHuecoPideConfirmacionTest(ReagendarBase):

    def test_elegir_hueco_enseña_el_modal_y_no_toca_la_reserva(self):
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(self.url_submit, self.datos())
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['mostrar_modal_duplicado'])
        self.assertEqual(resp.context['duplicado_token'], str(self.reserva.confirmacion_token))
        self.assertContains(resp, 'Sí, cancelar y agendar nueva')

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CONFIRMADA)
        self.assertEqual(Reserva.objects.count(), 1)

    def test_el_modal_lleva_la_identidad_de_la_reserva_aunque_manden_otra(self):
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(self.url_submit, self.datos(
                nombre_invitado='Colado Sinpagar', email_invitado='colado@gmail.com'))
        self.assertEqual(resp.context['email_invitado'], EMAIL_INVITADO)
        self.assertNotContains(resp, 'colado@gmail.com')

    def test_sin_hueco_valido_vuelve_al_formulario_sin_modal(self):
        resp = self.client.post(self.url_submit, self.datos(inicio_utc='no-es-fecha'))
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn('mostrar_modal_duplicado', resp.context)

    def test_con_el_telefono_mal_se_queda_en_el_dia_elegido(self):
        elegido = slot_futuro(dias=4, hora=12)
        resp = self.client.post(self.url_submit, self.datos(
            inicio_utc=iso(elegido), telefono_invitado=''))
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn('mostrar_modal_duplicado', resp.context)
        self.assertEqual(resp.context['fecha_iso'], elegido.date().isoformat())

    def test_aceptar_el_modal_cambia_la_reserva(self):
        """El modal hace el POST a /reemplazar/: la vieja se cancela y nace la nueva."""
        nuevo = slot_futuro(dias=4, hora=12)
        url = reverse('public_token:reemplazar_publica',
                      kwargs={'token': self.reserva.confirmacion_token})
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(url, {
                'inicio_utc': iso(nuevo),
                'nombre_invitado': NOMBRE_INVITADO,
                'email_invitado': EMAIL_INVITADO,
                'telefono_invitado': '+34 600123456',
            })
        self.assertEqual(resp.status_code, 302)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.CANCELADA)
        nueva = Reserva.objects.get(estado=Reserva.Estado.CONFIRMADA)
        self.assertEqual(nueva.inicio_utc, nuevo)
        self.assertEqual(nueva.email_invitado, EMAIL_INVITADO)
