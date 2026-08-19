"""
Envío por dominio propio y en texto plano.

Cada academia tiene que enviar desde su dominio (conquerblocks.com y compañía)
y no desde el de la app, y las respuestas del alumno tienen que caer en un buzón
que alguien lea. Eso son dos cosas distintas: el `From` y el `Reply-To`.

El caso que más importa es el último de este módulo: una plantilla sin dominio
asignado tiene que salir exactamente igual que antes de todo esto. Es lo que
protege a los correos que ya están funcionando.
"""
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings

from calendario.bookings.correos import _conexion, _enviar
from calendario.bookings.models import DominioRemitente, LogCorreo, PlantillaCorreo, Reserva
from tests.factories import (
    EMAIL_INVITADO, NOMBRE_INVITADO, crear_event_type, crear_host, slot_futuro,
)


BACKEND_MAILGUN = 'anymail.backends.mailgun.EmailBackend'


class CorreosDominioBase(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.et = crear_event_type(self.host)
        inicio = slot_futuro()
        self.reserva = Reserva.objects.create(
            event_type=self.et,
            host=self.host,
            inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=self.et.duracion_minutos),
            nombre_invitado=NOMBRE_INVITADO,
            email_invitado=EMAIL_INVITADO,
        )
        # Lo siembra la migración 0028, no lo creamos aquí: así los tests
        # comprueban de paso que los dominios llegan bien configurados.
        self.blocks = DominioRemitente.objects.get(dominio='conquerblocks.com')
        mail.outbox = []

    def _plantilla(self, **kwargs):
        datos = {
            'nombre': 'Plantilla test',
            'texto_encabezado': 'Tu sesión con {{nombre_host}}',
            'cuerpo': 'Hola {{nombre_invitado}}, nos vemos el {{fecha_hora}}.',
        }
        datos.update(kwargs)
        return PlantillaCorreo.objects.create(**datos)


class RemitenteYRespuestaTest(CorreosDominioBase):

    def test_con_dominio_usa_su_remitente_y_su_reply_to(self):
        plantilla = self._plantilla(dominio=self.blocks)

        self.assertTrue(_enviar(self.reserva, 'confirmacion_inv', EMAIL_INVITADO, plantilla))

        enviado = mail.outbox[0]
        self.assertEqual(enviado.from_email, 'Conquer Blocks <noreply@conquerblocks.com>')
        self.assertEqual(enviado.reply_to, ['contacto@conquerblocks.com'])

    def test_sin_reply_to_no_se_inventa_ninguno(self):
        self.blocks.reply_to = ''
        self.blocks.save()
        plantilla = self._plantilla(dominio=self.blocks)

        _enviar(self.reserva, 'confirmacion_inv', EMAIL_INVITADO, plantilla)

        self.assertEqual(mail.outbox[0].reply_to, [])

    def test_dominio_desactivado_vuelve_al_remitente_de_la_app(self):
        # Desactivar un dominio es la vía de escape si Mailgun lo bloquea: los
        # correos tienen que seguir saliendo, no dejar de enviarse.
        self.blocks.activo = False
        self.blocks.save()
        plantilla = self._plantilla(dominio=self.blocks)

        _enviar(self.reserva, 'confirmacion_inv', EMAIL_INVITADO, plantilla)

        from django.conf import settings
        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(mail.outbox[0].reply_to, [])


class RegionTest(CorreosDominioBase):
    """La región decide contra qué endpoint de Mailgun se envía.

    Un dominio de la UE atacado contra la API de EEUU responde 404 aunque esté
    verificado, así que esto no es un detalle cosmético.
    """

    @override_settings(EMAIL_BACKEND=BACKEND_MAILGUN, ANYMAIL={'MAILGUN_API_KEY': 'key-test'})
    def test_dominio_eu_apunta_al_endpoint_europeo(self):
        conexion = _conexion(self.blocks)
        self.assertEqual(conexion.api_url, 'https://api.eu.mailgun.net/v3/')
        self.assertEqual(conexion.sender_domain, 'conquerblocks.com')

    @override_settings(EMAIL_BACKEND=BACKEND_MAILGUN, ANYMAIL={'MAILGUN_API_KEY': 'key-test'})
    def test_dominio_us_apunta_al_endpoint_americano(self):
        calendario = DominioRemitente.objects.get(dominio='calendar.conquerx.com')
        conexion = _conexion(calendario)
        self.assertEqual(conexion.api_url, 'https://api.mailgun.net/v3/')

    def test_fuera_de_produccion_no_se_fuerza_mailgun(self):
        # En local y en los tests el backend es consola/locmem. Si forzáramos la
        # conexión de Mailgun, cada test intentaría salir a internet.
        self.assertIsNone(_conexion(self.blocks))


class FormatoTest(CorreosDominioBase):

    def test_texto_plano_va_sin_html(self):
        plantilla = self._plantilla(formato=PlantillaCorreo.Formato.TEXTO)

        _enviar(self.reserva, 'confirmacion_inv', EMAIL_INVITADO, plantilla)

        enviado = mail.outbox[0]
        self.assertEqual(enviado.alternatives, [])
        self.assertNotIn('<html', enviado.body.lower())
        self.assertNotIn('<table', enviado.body.lower())
        self.assertIn(NOMBRE_INVITADO, enviado.body)

    def test_html_conserva_las_dos_versiones(self):
        plantilla = self._plantilla(formato=PlantillaCorreo.Formato.HTML)

        _enviar(self.reserva, 'confirmacion_inv', EMAIL_INVITADO, plantilla)

        enviado = mail.outbox[0]
        self.assertEqual(len(enviado.alternatives), 1)
        cuerpo_html, tipo = enviado.alternatives[0]
        self.assertEqual(tipo, 'text/html')
        self.assertIn('<', cuerpo_html)
        # El texto plano sigue yendo como fallback para clientes sin HTML.
        self.assertIn(NOMBRE_INVITADO, enviado.body)

    def test_las_variables_se_sustituyen_tambien_en_texto_plano(self):
        plantilla = self._plantilla(
            formato=PlantillaCorreo.Formato.TEXTO,
            cuerpo='Hola {{nombre_invitado}}, tu sesión de {{duracion}} minutos.',
        )

        _enviar(self.reserva, 'confirmacion_inv', EMAIL_INVITADO, plantilla)

        cuerpo = mail.outbox[0].body
        self.assertNotIn('{{', cuerpo)
        self.assertIn(NOMBRE_INVITADO, cuerpo)
        self.assertIn(str(self.et.duracion_minutos), cuerpo)

    def test_el_log_guarda_lo_que_se_envio_de_verdad(self):
        plantilla = self._plantilla(formato=PlantillaCorreo.Formato.TEXTO)

        _enviar(self.reserva, 'confirmacion_inv', EMAIL_INVITADO, plantilla)

        log = LogCorreo.objects.get(reserva=self.reserva)
        self.assertNotIn('<table', log.html_content.lower())
        self.assertIn(NOMBRE_INVITADO, log.html_content)


class SinDominioSigueIgualTest(CorreosDominioBase):
    """Regresión. Miles de correos ya salen con la configuración de siempre."""

    def test_plantilla_sin_dominio_usa_el_remitente_global_y_manda_html(self):
        from django.conf import settings
        plantilla = self._plantilla()

        self.assertTrue(_enviar(self.reserva, 'confirmacion_inv', EMAIL_INVITADO, plantilla))

        enviado = mail.outbox[0]
        self.assertEqual(enviado.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(enviado.reply_to, [])
        self.assertEqual(enviado.to, [EMAIL_INVITADO])
        self.assertEqual(len(enviado.alternatives), 1)
        self.assertEqual(enviado.alternatives[0][1], 'text/html')

    def test_el_formato_por_defecto_es_html(self):
        self.assertEqual(self._plantilla().formato, PlantillaCorreo.Formato.HTML)

    def test_una_plantilla_nueva_no_trae_dominio(self):
        self.assertIsNone(self._plantilla().dominio)


class MigracionDominiosTest(TestCase):
    """Los dominios tienen que llegar ya configurados, no a mano uno por uno."""

    def test_las_tres_academias_estan_en_la_region_europea(self):
        for dominio in ('conquerblocks.com', 'conquerfinance.com', 'conquerlanguages.com'):
            with self.subTest(dominio=dominio):
                registro = DominioRemitente.objects.get(dominio=dominio)
                self.assertEqual(registro.region, DominioRemitente.Region.EU)
                self.assertEqual(registro.api_url, 'https://api.eu.mailgun.net/v3')

    def test_el_dominio_de_la_app_sigue_en_la_region_americana(self):
        registro = DominioRemitente.objects.get(dominio='calendar.conquerx.com')
        self.assertEqual(registro.region, DominioRemitente.Region.US)
        self.assertEqual(registro.api_url, 'https://api.mailgun.net/v3')

    def test_cada_academia_responde_a_su_propio_buzon(self):
        for dominio in ('conquerblocks.com', 'conquerfinance.com', 'conquerlanguages.com'):
            with self.subTest(dominio=dominio):
                registro = DominioRemitente.objects.get(dominio=dominio)
                self.assertEqual(registro.reply_to, f'contacto@{dominio}')
                self.assertIn(dominio, registro.from_email)

    def test_ninguna_plantilla_queda_asignada_por_la_migracion(self):
        # Asignar dominios automáticamente cambiaría de golpe correos que ya
        # están saliendo. Que lo haga una persona desde el admin.
        self.assertFalse(PlantillaCorreo.objects.exclude(dominio=None).exists())
