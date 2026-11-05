"""
Recordatorios por SMS: un SMS como máximo por recordatorio, mensaje por tipo de
evento con uno por defecto, y horas propias o las mismas del correo.
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import Mock, patch

import requests
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from calendario.bookings import sms
from calendario.bookings.models import ConfigCorreoEvento, LogSMS, PlantillaCorreo, Reserva
from calendario.event_types.forms import EventTypeForm
from calendario.users.models import User
from tests.factories import EMAIL_INVITADO, crear_event_type, crear_host


TELEFONO = '+34612345678'
CONFIG = dict(
    LABSMOBILE_USERNAME='usuario', LABSMOBILE_API_TOKEN='token',
    LABSMOBILE_SENDER='ConquerPass', LABSMOBILE_TEST=False,
    SITE_URL='https://calendar.conquerx.com',
)


def respuesta(status=200, code='0'):
    return Mock(status_code=status, text='', json=Mock(return_value={'code': code, 'message': 'x', 'subid': 'abc'}))


class TextoTest(TestCase):

    def test_quita_tildes_y_emojis_pero_conserva_lo_que_cabe_en_gsm(self):
        self.assertEqual(sms.limpiar_texto('Raúl Núñez, ¿vienes? 👍 “sí”'), 'Raul Nuñez, ¿vienes?  "si"')

    def test_el_mensaje_por_defecto_es_valido(self):
        sms.validar_plantilla(sms.MENSAJE_POR_DEFECTO)

    @override_settings(**CONFIG)
    def test_un_nombre_larguisimo_no_saca_el_mensaje_de_un_sms_ni_rompe_el_enlace(self):
        valores = sms.valores_de_ejemplo()
        valores['nombre_evento'] = 'Evento ' * 40
        mensaje = sms.componer_mensaje(sms.MENSAJE_POR_DEFECTO, valores)
        self.assertLessEqual(sms.longitud_sms(mensaje), 160)
        self.assertTrue(mensaje.endswith(valores['link_reagendar']))

    def test_rechaza_variables_inexistentes_y_textos_que_no_caben(self):
        with self.assertRaisesMessage(ValidationError, '{{inventada}}'):
            sms.validar_plantilla('Hola {{inventada}}')
        with self.assertRaisesMessage(ValidationError, 'No cabe'):
            sms.validar_plantilla('x' * 161)

    def test_los_caracteres_extendidos_cuentan_doble(self):
        self.assertEqual(sms.longitud_sms('€['), 4)

    def test_telefono(self):
        self.assertEqual(sms.normalizar_telefono('+34 612 34 56 78'), '34612345678')
        self.assertEqual(sms.normalizar_telefono('34612345678'), '34612345678')
        self.assertEqual(sms.normalizar_telefono('123'), '')


@override_settings(**CONFIG)
class EnvioTest(TestCase):

    def _enviar(self, **kwargs):
        with patch.object(sms.requests, 'post', **kwargs) as post:
            return sms.enviar_sms('34612345678', 'Hola'), post

    def test_payload_sin_long_ni_ucs2(self):
        resultado, post = self._enviar(return_value=respuesta())
        self.assertTrue(resultado.ok)
        self.assertEqual(post.call_args.kwargs['json'], {
            'message': 'Hola', 'tpoa': 'ConquerPass', 'recipient': [{'msisdn': '34612345678'}],
        })
        self.assertEqual(post.call_args.kwargs['auth'], ('usuario', 'token'))

    @override_settings(LABSMOBILE_TEST=True)
    def test_modo_prueba(self):
        _, post = self._enviar(return_value=respuesta())
        self.assertEqual(post.call_args.kwargs['json']['test'], '1')

    def test_http_200_con_codigo_de_error_no_cuenta_como_enviado(self):
        resultado, _ = self._enviar(return_value=respuesta(code='27'))
        self.assertFalse(resultado.ok)
        self.assertFalse(resultado.reintentable)

    def test_sin_saldo_detiene_la_pasada(self):
        self.assertTrue(self._enviar(return_value=respuesta(status=402))[0].detener_pasada)

    def test_tiempo_de_lectura_agotado_no_se_reintenta(self):
        resultado, _ = self._enviar(side_effect=requests.exceptions.ReadTimeout())
        self.assertFalse(resultado.reintentable)

    def test_sin_conexion_si_se_reintenta(self):
        resultado, _ = self._enviar(side_effect=requests.exceptions.ConnectTimeout())
        self.assertTrue(resultado.reintentable)


@override_settings(**CONFIG)
class ProcesarBase(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        self.et.nombre = 'Admisión'
        self.et.sms_activo = True
        self.et.save()

    def _reserva(self, horas, creada_hace_dias=30, telefono=TELEFONO):
        inicio = datetime.now(dt_timezone.utc) + timedelta(hours=horas)
        reserva = Reserva.objects.create(
            event_type=self.et, host=self.host, inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=30), nombre_invitado='Raúl Pérez',
            email_invitado=EMAIL_INVITADO, telefono_invitado=telefono,
            timezone_invitado='Europe/Madrid',
        )
        Reserva.objects.filter(pk=reserva.pk).update(
            fecha_creacion=datetime.now(dt_timezone.utc) - timedelta(days=creada_hace_dias),
        )
        reserva.refresh_from_db()
        return reserva

    def _procesar(self, **kwargs):
        kwargs.setdefault('return_value', respuesta())
        with patch.object(sms.requests, 'post', **kwargs) as post:
            resultado = sms.procesar_recordatorios()
        return resultado, post


class MomentoDeEnvioTest(ProcesarBase):

    def test_fuera_de_ventana_no_se_envia(self):
        self._reserva(horas=30)
        _, post = self._procesar()
        post.assert_not_called()

    def test_recordatorio_de_24h_y_un_solo_sms_aunque_el_cron_repita(self):
        reserva = self._reserva(horas=23)
        _, post = self._procesar()
        self.assertEqual(post.call_count, 1)
        _, post = self._procesar()
        post.assert_not_called()
        reserva.refresh_from_db()
        self.assertTrue(reserva.sms_recordatorio_1_procesado)
        self.assertFalse(reserva.sms_recordatorio_2_procesado)

    def test_luego_sale_el_de_1h(self):
        reserva = self._reserva(horas=0.5)
        Reserva.objects.filter(pk=reserva.pk).update(sms_recordatorio_1_procesado=True)
        _, post = self._procesar()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(LogSMS.objects.get().tipo, 'recordatorio_2')

    def test_si_tocan_dos_a_la_vez_solo_sale_el_mas_cercano(self):
        reserva = self._reserva(horas=0.5)
        _, post = self._procesar()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(LogSMS.objects.get().tipo, 'recordatorio_2')
        reserva.refresh_from_db()
        self.assertTrue(reserva.sms_recordatorio_1_procesado)

    def test_reserva_creada_con_la_ventana_abierta_no_recibe_ese_recordatorio(self):
        self._reserva(horas=5, creada_hace_dias=0)
        _, post = self._procesar()
        post.assert_not_called()

    def test_horas_personalizadas(self):
        self.et.sms_usar_horas_correo = False
        self.et.sms_recordatorio_1_horas = 48
        self.et.sms_recordatorio_2_horas = None
        self.et.save()
        self._reserva(horas=40)
        self._reserva(horas=0.5)
        _, post = self._procesar()
        self.assertEqual(post.call_count, 2)
        self.assertEqual(set(LogSMS.objects.values_list('tipo', flat=True)), {'recordatorio_1'})

    def test_mismas_horas_que_el_correo(self):
        plantilla = PlantillaCorreo.objects.create(
            nombre='P', texto_encabezado='x', cuerpo='x',
            recordatorio_1_activo=True, recordatorio_1_horas=6, recordatorio_2_activo=False,
        )
        ConfigCorreoEvento.objects.create(event_type=self.et, plantilla_recordatorio=plantilla)
        self._reserva(horas=10)
        self.assertEqual(self._procesar()[1].call_count, 0)
        self._reserva(horas=5)
        self.assertEqual(self._procesar()[1].call_count, 1)

    def test_evento_sin_activar_o_reserva_cancelada_o_sin_telefono(self):
        cancelada = self._reserva(horas=2)
        Reserva.objects.filter(pk=cancelada.pk).update(estado=Reserva.Estado.CANCELADA)
        self._reserva(horas=2, telefono='')
        _, post = self._procesar()
        post.assert_not_called()
        self.et.sms_activo = False
        self.et.save()
        self._reserva(horas=2)
        post = self._procesar()[1]
        post.assert_not_called()


class FallosTest(ProcesarBase):

    def test_fallo_temporal_se_reintenta_hasta_el_tope(self):
        reserva = self._reserva(horas=23)
        for _ in range(sms.MAX_INTENTOS + 2):
            self._procesar(return_value=respuesta(status=500))
        reserva.refresh_from_db()
        self.assertEqual(reserva.sms_recordatorio_1_intentos, sms.MAX_INTENTOS)
        self.assertEqual(LogSMS.objects.count(), sms.MAX_INTENTOS)

    def test_respuesta_perdida_no_se_reintenta_para_no_duplicar(self):
        self._reserva(horas=23)
        self._procesar(side_effect=requests.exceptions.ReadTimeout())
        _, post = self._procesar()
        post.assert_not_called()

    def test_sin_saldo_para_la_pasada_y_no_gasta_intentos(self):
        primera = self._reserva(horas=22)
        self._reserva(horas=23)
        resultado, post = self._procesar(return_value=respuesta(status=402))
        self.assertEqual(post.call_count, 1)
        self.assertEqual(resultado, (0, 1, True))
        primera.refresh_from_db()
        self.assertFalse(primera.sms_recordatorio_1_procesado)
        self.assertEqual(primera.sms_recordatorio_1_intentos, 0)
        self.assertEqual(self._procesar()[0], (2, 0, False))

    def test_telefono_invalido_queda_en_el_log_sin_llamar_al_proveedor(self):
        self._reserva(horas=23, telefono='123')
        _, post = self._procesar()
        post.assert_not_called()
        log = LogSMS.objects.get()
        self.assertFalse(log.exitoso)
        self.assertIn('Teléfono no válido', log.error_detalle)


class MensajeTest(ProcesarBase):

    def test_vacio_usa_el_mensaje_por_defecto_sin_tildes_y_con_enlace_corto(self):
        reserva = self._reserva(horas=23)
        _, post = self._procesar()
        reserva.refresh_from_db()
        mensaje = post.call_args.kwargs['json']['message']
        self.assertIn('Hola Raul, recuerda tu cita Admision el ', mensaje)
        self.assertIn('(Madrid)', mensaje)
        self.assertTrue(mensaje.endswith(f'https://calendar.conquerx.com/s/{reserva.sms_codigo}'))
        self.assertLessEqual(sms.longitud_sms(mensaje), 160)

    def test_mensaje_propio_del_evento(self):
        self.et.sms_mensaje = 'Te esperamos {{nombre}} a las {{hora}}'
        self.et.save()
        reserva = self._reserva(horas=23)
        _, post = self._procesar()
        self.assertTrue(post.call_args.kwargs['json']['message'].startswith('Te esperamos Raul a las '))
        reserva.refresh_from_db()
        self.assertIsNone(reserva.sms_codigo)


class EnlaceCortoTest(ProcesarBase):

    def test_redirige_a_reagendar_y_cancelar(self):
        reserva = self._reserva(horas=23)
        Reserva.objects.filter(pk=reserva.pk).update(sms_codigo='abcDEF1234')
        token = reserva.confirmacion_token
        self.assertRedirects(self.client.get('/s/abcDEF1234'), f'/r/{token}/reagendar/', fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/s/abcDEF1234/c'), f'/r/{token}/cancelar/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/s/noexiste00').status_code, 404)


class ComandoTest(ProcesarBase):

    def test_el_cron_de_siempre_tambien_envia_los_sms(self):
        self._reserva(horas=23)
        with patch.object(sms.requests, 'post', return_value=respuesta()) as post:
            call_command('enviar_recordatorios', pausa=0, verbosity=0)
        self.assertEqual(post.call_count, 1)

    @override_settings(LABSMOBILE_USERNAME='', LABSMOBILE_API_TOKEN='')
    def test_sin_credenciales_no_consume_los_recordatorios(self):
        reserva = self._reserva(horas=23)
        with patch.object(sms.requests, 'post') as post:
            call_command('enviar_recordatorios', pausa=0, verbosity=0)
        post.assert_not_called()
        reserva.refresh_from_db()
        self.assertFalse(reserva.sms_recordatorio_1_procesado)


class ValidacionEventoTest(ProcesarBase):

    def _validar(self, **campos):
        for campo, valor in campos.items():
            setattr(self.et, campo, valor)
        self.et.clean()

    def test_horas_personalizadas_exigen_al_menos_una(self):
        with self.assertRaisesMessage(ValidationError, 'al menos un SMS'):
            self._validar(sms_usar_horas_correo=False, sms_recordatorio_1_horas=None, sms_recordatorio_2_horas=None)

    def test_horas_iguales_no_valen(self):
        with self.assertRaisesMessage(ValidationError, 'misma hora'):
            self._validar(sms_usar_horas_correo=False, sms_recordatorio_1_horas=3, sms_recordatorio_2_horas=3)

    def test_mensaje_largo_no_se_guarda(self):
        with self.assertRaisesMessage(ValidationError, 'No cabe'):
            self._validar(sms_mensaje='x' * 200)

    def test_el_formulario_del_panel_expone_los_campos(self):
        form = EventTypeForm(instance=self.et)
        for campo in ('sms_activo', 'sms_mensaje', 'sms_usar_horas_correo',
                      'sms_recordatorio_1_horas', 'sms_recordatorio_2_horas'):
            self.assertIn(campo, form.fields)
        self.assertEqual(form.sms_config_js['defecto'], sms.MENSAJE_POR_DEFECTO)


class PantallasTest(ProcesarBase):

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(
            username='admin.sms', email='admin.sms@test.com', password='x',
        )
        self.client.force_login(self.admin)

    def test_el_panel_muestra_la_casilla_y_la_vista_previa(self):
        url = reverse('panel_event_types:event_type_update', args=[self.et.pk])
        contenido = self.client.get(url).content.decode()
        self.assertIn('name="sms_activo"', contenido)
        self.assertIn('name="sms_mensaje"', contenido)
        self.assertIn('id="sms-config"', contenido)
        self.assertIn('data-sms-variable="link_reagendar"', contenido)

    def test_el_admin_muestra_los_campos_y_el_log(self):
        url = reverse('admin:event_types_eventtype_change', args=[self.et.pk])
        self.assertContains(self.client.get(url), 'name="sms_mensaje"')
        reserva = self._reserva(horas=23)
        log = LogSMS.objects.create(
            reserva=reserva, tipo='recordatorio_1', telefono='34612345678', mensaje='Hola', exitoso=True,
        )
        self.assertContains(self.client.get(reverse('admin:bookings_logsms_changelist')), '34612345678')
        self.assertEqual(
            self.client.get(reverse('admin:bookings_logsms_change', args=[log.pk])).status_code, 200,
        )
