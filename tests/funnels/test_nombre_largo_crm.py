"""
Un nombre largo no puede costar la prellamada entera.

Caso real de producción: la Prellamada 25636 llegó con un `nombre` de 160
caracteres —alguien pegó un texto en la casilla del nombre— y el CRM devolvió
`400 value too long for type character varying(140)`. La tarea agotó sus
reintentos y esa prellamada no llegó nunca: siete eventos en Sentry, y detrás
de cada uno un lead que el equipo comercial no vio.

El desajuste es exacto y estaba esperando a que alguien lo pisara:
`Prellamada.nombre` es varchar(160) en el calendario y `PreSchedule.lead_name`
es varchar(140) en el CRM. Cualquier nombre de 141 a 160 caracteres se guarda
aquí sin problema y revienta allí.

Mismo criterio que con el tracking desmedido (FUNNELS-67): el dato se recorta a
lo que cabe y el lead llega. Un nombre de 140 caracteres ya es absurdo; perder
la prellamada por los 20 que sobran, más.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from calendario.funnels import crm_preschedule
from calendario.funnels.models import FunnelForm, Prellamada


# El límite que impone el CRM en `PreSchedule.lead_name`.
LIMITE_DEL_CRM = 140


class RespuestaFalsa:
    status_code = 200
    text = '{"ok": true}'


@override_settings(CRM_API_KEY='clave-de-test', CRM_BASE_URL='https://crm.ejemplo.com')
class NombreLargoTest(TestCase):

    def setUp(self):
        # Los seeds ya traen los funnels reales, así que se usa uno propio.
        self.funnel = FunnelForm.objects.create(
            slug='funnel-de-test', key='funnel-de-test', activo=True, config={},
        )

    def _prellamada(self, nombre):
        return Prellamada.objects.create(
            funnel=self.funnel,
            nombre=nombre,
            email='lead@ejemplo.com',
            telefono='+34600000000',
            tracking={'journey_id': 'jrn_test'},
        )

    def _payload_enviado(self, prellamada):
        with patch('requests.post', return_value=RespuestaFalsa()) as post:
            crm_preschedule.push_pre_schedule(prellamada)
        return post.call_args.kwargs['json']

    def test_el_nombre_que_no_cabe_en_el_crm_se_recorta(self):
        """La réplica de la Prellamada 25636: 160 caracteres, 400 del CRM."""
        largo = 'A' * 160
        payload = self._payload_enviado(self._prellamada(largo))

        self.assertLessEqual(
            len(payload['lead_name']), LIMITE_DEL_CRM,
            'se manda un lead_name que no cabe en el CRM: responde 400 y la '
            'prellamada se pierde entera',
        )
        # Y se recorta, no se vacía: el nombre sigue sirviendo para identificar.
        self.assertTrue(payload['lead_name'].startswith('AAAA'))

    def test_un_nombre_normal_viaja_intacto(self):
        payload = self._payload_enviado(self._prellamada('Patricia Fernández'))
        self.assertEqual(payload['lead_name'], 'Patricia Fernández')

    def test_las_respuestas_largas_no_se_tocan(self):
        """En el CRM los q*_answer son TextField: ahí no hay nada que recortar.

        Importa distinguirlo: la misma prellamada traía una respuesta de 328
        caracteres y otra de 188, y no son las que provocaban el 400. Recortarlas
        sería perder información del lead sin motivo.
        """
        self.funnel.config = {'q_order': ['motivo']}
        self.funnel.save(update_fields=['config'])
        prellamada = self._prellamada('Nombre Normal')
        prellamada.respuestas = {'motivo': 'B' * 328}
        prellamada.save(update_fields=['respuestas'])

        payload = self._payload_enviado(prellamada)
        self.assertEqual(len(payload['q1_answer']), 328)
