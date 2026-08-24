"""
Tipos de evento «solo alumnos», embebidos en el LMS de la academia.

La página de reserva se mete por iframe dentro de la academia. Para que solo
reserven los alumnos, el LMS firma un token con un secreto compartido y esta app
se limita a verificar la firma: aquí no hay copia de los alumnos ni consulta
ninguna al LMS.

Lo que cubren estos tests, en orden:

  * los eventos públicos siguen comportándose exactamente igual que antes;
  * sin token, con un token falso o con uno caducado no se reserva ni se ve la
    disponibilidad;
  * la identidad de la reserva sale del token y no del formulario, que es lo que
    hace inútil compartir el enlace: la reserva queda a nombre del alumno;
  * las cabeceras dejan pintar la página dentro del iframe;
  * los tres flujos públicos (individual, equipo y enlace único) están cubiertos,
    porque un control a medias daría por protegido un evento que no lo está.
"""
from datetime import timedelta
from unittest.mock import patch

from django.core import signing
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from calendario.bookings.models import Reserva
from calendario.event_types.models import EnlaceUnico, EventType
from tests.factories import (
    EMAIL_INVITADO, NOMBRE_INVITADO,
    crear_disponibilidad, crear_event_type, crear_host, slot_futuro,
)


SECRETO = 'secreto-de-pruebas-compartido-con-el-lms'
SALT = 'lms-embed'
ORIGEN_LMS = 'https://academia.example.com'

EMAIL_ALUMNO = 'alumna@academia.example.com'
NOMBRE_ALUMNO = 'Carmen Ruiz'

# Sin los mocks, crear_reserva sale a Google Calendar de verdad.
MOCKS_GCAL = [
    patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False),
    patch('calendario.bookings.services.crear_evento_google'),
    patch('calendario.bookings.services.obtener_busy_intervalos', return_value=[]),
]


def token_lms(email=EMAIL_ALUMNO, nombre=NOMBRE_ALUMNO, telefono='', **extra):
    """Un token como el que emitiría el LMS."""
    payload = {'uid': 41, 'email': email, 'nombre': nombre}
    if telefono:
        payload['telefono'] = telefono
    payload.update(extra)
    return signing.dumps(payload, key=SECRETO, salt=SALT)


@override_settings(
    EMBED_LMS_SECRET=SECRETO,
    EMBED_LMS_SALT=SALT,
    EMBED_LMS_MAX_AGE=3600,
    EMBED_LMS_ORIGENES=[ORIGEN_LMS],
)
class EmbedBase(TestCase):

    def setUp(self):
        self.client = Client()
        self.host = crear_host()
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)

        self.publico = crear_event_type(self.host, nombre='Llamada abierta')
        self.privado = crear_event_type(self.host, nombre='Tutoría de alumnos')
        self.privado.acceso = EventType.ACCESO_ACADEMIA
        self.privado.save(update_fields=['acceso'])

    # -- URLs --------------------------------------------------------------
    def url_pagina(self, et):
        return reverse('public_booking:booking_page', kwargs={
            'user_slug': self.host.slug, 'event_type_slug': et.slug})

    def url_submit(self, et):
        return reverse('public_booking:booking_submit', kwargs={
            'user_slug': self.host.slug, 'event_type_slug': et.slug})

    def url_slots(self, et):
        return reverse('public_booking:slots_mes_json', kwargs={
            'user_slug': self.host.slug, 'event_type_slug': et.slug})

    def datos_reserva(self, **extra):
        datos = {
            'inicio_utc': slot_futuro(dias=3, hora=14).strftime('%Y-%m-%dT%H:%M:%S+00:00'),
            'nombre_invitado': NOMBRE_INVITADO,
            'email_invitado': EMAIL_INVITADO,
            'telefono_invitado': '+34 600123456',
        }
        datos.update(extra)
        return datos


# ---------------------------------------------------------------------------
# 1. Lo que ya existía no cambia
# ---------------------------------------------------------------------------

class EventosPublicosIntactosTest(EmbedBase):

    def test_el_defecto_es_publico(self):
        """Un event type recién creado no exige token: las filas viejas tampoco."""
        self.assertEqual(self.publico.acceso, EventType.ACCESO_PUBLICO)
        self.assertFalse(self.publico.solo_alumnos)

    def test_pagina_publica_sigue_abierta_sin_token(self):
        resp = self.client.get(self.url_pagina(self.publico))
        self.assertEqual(resp.status_code, 200)

    def test_pagina_publica_no_bloquea_los_campos(self):
        resp = self.client.get(self.url_pagina(self.publico))
        self.assertFalse(resp.context.get('campos_identidad_bloqueados', False))

    def test_slots_publicos_siguen_abiertos(self):
        resp = self.client.get(self.url_slots(self.publico))
        self.assertEqual(resp.status_code, 200)

    def test_la_pagina_publica_no_se_deja_embeber(self):
        """Solo los eventos de la academia relajan el antiframe."""
        resp = self.client.get(self.url_pagina(self.publico))
        self.assertNotIn('Content-Security-Policy', resp)

    def test_reserva_publica_usa_el_email_del_formulario(self):
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(self.url_submit(self.publico), self.datos_reserva())
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Reserva.objects.latest('id').email_invitado, EMAIL_INVITADO)


# ---------------------------------------------------------------------------
# 2. Sin token válido no se entra
# ---------------------------------------------------------------------------

class SinTokenNoSeEntraTest(EmbedBase):

    def test_sin_token_la_pagina_se_cierra(self):
        resp = self.client.get(self.url_pagina(self.privado))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.context['motivo'], 'ausente')

    def test_sin_token_no_se_ve_ni_la_disponibilidad(self):
        """El calendario de huecos también va detrás del control."""
        resp = self.client.get(self.url_slots(self.privado))
        self.assertEqual(resp.status_code, 403)

    def test_sin_token_no_se_puede_reservar_por_POST(self):
        """Saltarse la página e ir directo al POST tampoco vale."""
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(self.url_submit(self.privado), self.datos_reserva())
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Reserva.objects.exists())

    def test_token_firmado_con_otro_secreto(self):
        """Quien no tiene el secreto no puede fabricar un token."""
        falso = signing.dumps({'email': 'colado@gmail.com', 'nombre': 'Colado'},
                              key='secreto-inventado', salt=SALT)
        resp = self.client.get(self.url_pagina(self.privado) + f'?t={falso}')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.context['motivo'], 'invalido')

    def test_token_con_el_salt_cambiado(self):
        """El salt es parte del acuerdo: si no coincide, no vale."""
        otro = signing.dumps({'email': EMAIL_ALUMNO, 'nombre': NOMBRE_ALUMNO},
                             key=SECRETO, salt='otro-salt')
        resp = self.client.get(self.url_pagina(self.privado) + f'?t={otro}')
        self.assertEqual(resp.status_code, 403)

    def test_token_manipulado(self):
        """Cambiarle una letra al payload invalida la firma."""
        bueno = token_lms()
        trucado = ('X' if bueno[0] != 'X' else 'Y') + bueno[1:]
        resp = self.client.get(self.url_pagina(self.privado) + f'?t={trucado}')
        self.assertEqual(resp.status_code, 403)

    @override_settings(EMBED_LMS_MAX_AGE=-1)
    def test_token_caducado(self):
        """El enlace guardado en marcadores deja de servir."""
        resp = self.client.get(self.url_pagina(self.privado) + f'?t={token_lms()}')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.context['motivo'], 'caducado')

    @override_settings(EMBED_LMS_SECRET='')
    def test_sin_secreto_configurado_se_cierra_no_se_abre(self):
        """Desplegar sin la variable no puede dejar el evento abierto a cualquiera."""
        resp = self.client.get(self.url_pagina(self.privado) + f'?t={token_lms()}')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.context['motivo'], 'sin_configurar')

    def test_token_sin_email_no_vale(self):
        """Firma buena pero payload inservible: es un fallo del LMS, no se pasa."""
        cojo = signing.dumps({'uid': 41, 'nombre': NOMBRE_ALUMNO}, key=SECRETO, salt=SALT)
        resp = self.client.get(self.url_pagina(self.privado) + f'?t={cojo}')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.context['motivo'], 'incompleto')

    def test_la_pagina_de_bloqueo_si_se_deja_embeber(self):
        """Si no, dentro de la academia se vería un hueco en blanco."""
        resp = self.client.get(self.url_pagina(self.privado))
        self.assertIn(ORIGEN_LMS, resp['Content-Security-Policy'])


# ---------------------------------------------------------------------------
# 3. Con token válido se reserva, y con la identidad del token
# ---------------------------------------------------------------------------

class ConTokenValidoTest(EmbedBase):

    def test_la_pagina_abre(self):
        resp = self.client.get(self.url_pagina(self.privado) + f'?t={token_lms()}')
        self.assertEqual(resp.status_code, 200)

    def test_los_datos_del_alumno_salen_puestos_y_bloqueados(self):
        resp = self.client.get(self.url_pagina(self.privado) + f'?t={token_lms()}')
        self.assertEqual(resp.context['email_invitado'], EMAIL_ALUMNO)
        self.assertEqual(resp.context['nombre_invitado'], NOMBRE_ALUMNO)
        self.assertTrue(resp.context['campos_identidad_bloqueados'])
        self.assertContains(resp, 'readonly')

    def test_el_telefono_se_prellena_pero_editable(self):
        """Falsear el teléfono no da acceso a nada: solo se fastidia quien lo hace."""
        t = token_lms(telefono='+34 600999888')
        resp = self.client.get(self.url_pagina(self.privado) + f'?t={t}')
        self.assertEqual(resp.context['telefono_invitado'], '+34 600999888')

    def test_el_token_viaja_al_formulario_y_a_los_slots(self):
        """Si no sobreviviera, el envío se caería con un 403."""
        t = token_lms()
        resp = self.client.get(self.url_pagina(self.privado) + f'?t={t}')
        self.assertIn('t=', resp.context['form_action_url'])
        self.assertIn('t=', resp.context['slots_url'])

    def test_los_slots_se_ven_con_token(self):
        resp = self.client.get(self.url_slots(self.privado) + f'?t={token_lms()}')
        self.assertEqual(resp.status_code, 200)

    def test_la_pagina_se_deja_embeber_en_la_academia(self):
        resp = self.client.get(self.url_pagina(self.privado) + f'?t={token_lms()}')
        self.assertIn(ORIGEN_LMS, resp['Content-Security-Policy'])
        self.assertIn('frame-ancestors', resp['Content-Security-Policy'])
        self.assertNotIn('X-Frame-Options', resp)

    def test_reserva_con_token(self):
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(
                self.url_submit(self.privado) + f'?t={token_lms()}',
                self.datos_reserva(),
            )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Reserva.objects.count(), 1)

    def test_la_reserva_se_crea_con_la_identidad_del_token(self):
        """El corazón del diseño.

        Aunque el enlace se filtre y otra persona lo use, la reserva queda a
        nombre del alumno y el correo de confirmación le llega a él. Compartirlo
        no sirve de nada y encima es trazable.
        """
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(
                self.url_submit(self.privado) + f'?t={token_lms()}',
                self.datos_reserva(
                    nombre_invitado='Colado Sinpagar',
                    email_invitado='colado@gmail.com',
                ),
            )
        self.assertEqual(resp.status_code, 302)
        reserva = Reserva.objects.latest('id')
        self.assertEqual(reserva.email_invitado, EMAIL_ALUMNO)
        self.assertEqual(reserva.nombre_invitado, NOMBRE_ALUMNO)

    def test_el_post_no_necesita_cookie_csrf(self):
        """En un iframe cross-site el navegador no manda la cookie csrftoken.

        Sin la exención, el envío moriría con un 403 que nadie sabría explicar.
        """
        cliente = Client(enforce_csrf_checks=True)
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = cliente.post(
                self.url_submit(self.privado) + f'?t={token_lms()}',
                self.datos_reserva(),
            )
        self.assertEqual(resp.status_code, 302)

    def test_sin_token_el_csrf_sigue_exigiendose(self):
        """La exención es solo para el embebido, no un agujero general."""
        cliente = Client(enforce_csrf_checks=True)
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = cliente.post(self.url_submit(self.publico), self.datos_reserva())
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# 4. Los otros dos flujos públicos
# ---------------------------------------------------------------------------

class FlujoDeEquipoTest(EmbedBase):

    def setUp(self):
        super().setUp()
        self.privado.slug_equipo = 'tutoria-alumnos'
        self.privado.save(update_fields=['slug_equipo'])

    def url(self, nombre):
        return reverse(f'public_team:{nombre}', kwargs={'slug_equipo': 'tutoria-alumnos'})

    def test_sin_token_no_abre(self):
        self.assertEqual(self.client.get(self.url('booking_page')).status_code, 403)

    def test_sin_token_no_hay_slots(self):
        self.assertEqual(self.client.get(self.url('slots_mes_json')).status_code, 403)

    def test_sin_token_no_se_reserva(self):
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(self.url('booking_submit'), self.datos_reserva())
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Reserva.objects.exists())

    def test_con_token_abre_y_manda_la_identidad_del_token(self):
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(
                self.url('booking_submit') + f'?t={token_lms()}',
                self.datos_reserva(email_invitado='colado@gmail.com'),
            )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Reserva.objects.latest('id').email_invitado, EMAIL_ALUMNO)


class FlujoEnlaceUnicoTest(EmbedBase):

    def setUp(self):
        super().setUp()
        self.enlace = EnlaceUnico.objects.create(
            event_type=self.privado, creado_por=self.host)

    def url(self, nombre):
        return reverse(f'public_enlace_unico:{nombre}',
                       kwargs={'token': str(self.enlace.token)})

    def test_sin_token_no_abre(self):
        self.assertEqual(self.client.get(self.url('booking_page')).status_code, 403)

    def test_sin_token_no_hay_slots(self):
        self.assertEqual(self.client.get(self.url('slots_mes_json')).status_code, 403)

    def test_sin_token_no_se_reserva(self):
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(self.url('booking_submit'), self.datos_reserva())
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Reserva.objects.exists())

    def test_con_token_manda_la_identidad_del_token(self):
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            resp = self.client.post(
                self.url('booking_submit') + f'?t={token_lms()}',
                self.datos_reserva(email_invitado='colado@gmail.com'),
            )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Reserva.objects.latest('id').email_invitado, EMAIL_ALUMNO)


# ---------------------------------------------------------------------------
# 5. Reagendar desde el correo
# ---------------------------------------------------------------------------

class ReagendarNoCambiaLaIdentidadTest(EmbedBase):
    """A esta vista se llega con el enlace del correo, no con el token del LMS.

    Si el formulario mandara, bastaría un POST a mano para pasarle la clase a
    alguien de fuera de la academia.
    """

    def setUp(self):
        super().setUp()
        inicio = slot_futuro(dias=2, hora=11)
        self.reserva = Reserva.objects.create(
            event_type=self.privado,
            host=self.host,
            inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=self.privado.duracion_minutos),
            nombre_invitado=NOMBRE_ALUMNO,
            email_invitado=EMAIL_ALUMNO,
        )

    def test_no_se_puede_cambiar_el_email_al_reagendar(self):
        url = reverse('public_token:reemplazar_publica',
                      kwargs={'token': self.reserva.confirmacion_token})
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            self.client.post(url, self.datos_reserva(
                inicio_utc=slot_futuro(dias=4, hora=12).strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                email_invitado='colado@gmail.com',
                nombre_invitado='Colado Sinpagar',
            ))
        nueva = Reserva.objects.filter(estado=Reserva.Estado.CONFIRMADA).latest('id')
        self.assertEqual(nueva.email_invitado, EMAIL_ALUMNO)
        self.assertEqual(nueva.nombre_invitado, NOMBRE_ALUMNO)

    def test_en_un_evento_publico_si_se_puede(self):
        """La restricción es solo de los eventos de la academia."""
        inicio = slot_futuro(dias=2, hora=15)
        reserva = Reserva.objects.create(
            event_type=self.publico, host=self.host, inicio_utc=inicio,
            fin_utc=inicio + timedelta(minutes=self.publico.duracion_minutos),
            nombre_invitado=NOMBRE_INVITADO, email_invitado=EMAIL_INVITADO,
        )
        url = reverse('public_token:reemplazar_publica',
                      kwargs={'token': reserva.confirmacion_token})
        with MOCKS_GCAL[0], MOCKS_GCAL[1], MOCKS_GCAL[2]:
            self.client.post(url, self.datos_reserva(
                inicio_utc=slot_futuro(dias=5, hora=16).strftime('%Y-%m-%dT%H:%M:%S+00:00'),
                email_invitado='otro@ejemplo.com',
                nombre_invitado='Otro Nombre',
            ))
        nueva = Reserva.objects.filter(
            event_type=self.publico, estado=Reserva.Estado.CONFIRMADA).latest('id')
        self.assertEqual(nueva.email_invitado, 'otro@ejemplo.com')


# ---------------------------------------------------------------------------
# 6. Compatibilidad con el LMS
# ---------------------------------------------------------------------------

class CompatibilidadConElLmsTest(TestCase):
    """El LMS va en Django 5.2 y esta app en 4.2.

    El formato de `signing` es el mismo, pero conviene tener fijado por escrito
    con qué parámetros se firma: si alguno de los dos cambia el salt o se olvida
    de pasar `key=`, la firma deja de validar sin ninguna pista de por qué (sin
    `key=` cada app usaría su propio SECRET_KEY, que son distintos).
    """

    @override_settings(EMBED_LMS_SECRET=SECRETO, EMBED_LMS_SALT=SALT,
                       EMBED_LMS_MAX_AGE=3600)
    def test_un_token_del_lms_se_lee_aqui(self):
        from calendario.bookings.embed import leer_token

        # Firmado "desde fuera", con los mismos parámetros acordados.
        crudo = signing.dumps(
            {'uid': 41, 'email': EMAIL_ALUMNO, 'nombre': NOMBRE_ALUMNO,
             'telefono': '+34 600111222'},
            key=SECRETO, salt=SALT,
        )
        datos = leer_token(crudo)
        self.assertEqual(datos['email'], EMAIL_ALUMNO)
        self.assertEqual(datos['nombre'], NOMBRE_ALUMNO)
        self.assertEqual(datos['telefono'], '+34 600111222')
        self.assertEqual(datos['uid'], 41)

    @override_settings(EMBED_LMS_SECRET=SECRETO, EMBED_LMS_SALT=SALT,
                       EMBED_LMS_MAX_AGE=3600)
    def test_firmar_token_y_leerlo_dan_la_vuelta_completa(self):
        from calendario.bookings.embed import firmar_token, leer_token

        datos = leer_token(firmar_token({'email': EMAIL_ALUMNO, 'nombre': NOMBRE_ALUMNO}))
        self.assertEqual(datos['email'], EMAIL_ALUMNO)
