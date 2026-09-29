"""
Respaldo en Supabase: nada de lo que manda el frontend se pierde, aunque cambie.

Antes se guardaba una lista fija de columnas: si el frontend mandaba un campo
nuevo (o con otro nombre, como el `phone` de julio), desaparecía en silencio.
Ahora va el request entero en crudo y el objeto con todos sus campos.
"""
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from calendario.core import respaldo
from calendario.leads.models import Lead

ENCOLAR = 'calendario.core.tasks.process_request_supabase.delay'


def _cuerpo():
    return {'name': 'Ana', 'email': 'ana@ejemplo.com', 'funnel': 'cb-eu',
            'campo_que_aun_no_existe': {'lo que sea': [1, 2]}}


class CapturaDeRequestsTest(TestCase):

    def _post_lead(self, **extra):
        with patch(ENCOLAR) as encolar, patch('calendario.leads.tasks.dispatch_lead_tasks'):
            resp = self.client.post('/f/api/lead/', data=json.dumps(_cuerpo()),
                                    content_type='application/json', **extra)
        return resp, encolar

    def test_guarda_el_request_entero_con_campos_desconocidos(self):
        resp, encolar = self._post_lead(HTTP_CF_CONNECTING_IP='1.2.3.4', HTTP_CF_IPCOUNTRY='ES',
                                        HTTP_X_CUALQUIER_COSA='sí', HTTP_COOKIE='_ga=GA1.2.3')
        tabla, fila = encolar.call_args.args
        self.assertEqual(tabla, 'requests')
        self.assertEqual(fila['body'], _cuerpo())  # incluido el campo que el modelo no conoce
        self.assertEqual(fila['ip'], '1.2.3.4')
        self.assertEqual(fila['pais'], 'ES')
        self.assertEqual(fila['headers']['X-Cualquier-Cosa'], 'sí')
        self.assertIn('_ga=GA1.2.3', fila['headers']['Cookie'])  # no se quita nada
        self.assertEqual(fila['metodo'], 'POST')
        self.assertEqual(fila['ruta'], '/f/api/lead/')
        self.assertEqual(fila['status'], resp.status_code)

    def test_se_enlaza_con_el_lead_que_genero(self):
        with patch(ENCOLAR) as encolar, patch('celery.app.task.Task.apply_async'):
            self.client.post('/f/api/lead/', data=json.dumps(_cuerpo()), content_type='application/json')
        _, fila = encolar.call_args.args
        lead = Lead.objects.get()
        self.assertIn(['lead', lead.pk], fila['objetos'])

    def test_tambien_las_peticiones_rechazadas(self):
        with patch(ENCOLAR) as encolar:
            resp = self.client.post('/f/api/lead/', data='esto no es json', content_type='text/plain')
        tabla, fila = encolar.call_args.args
        self.assertGreaterEqual(resp.status_code, 400)
        self.assertEqual(fila['status'], resp.status_code)
        self.assertEqual(fila['body_texto'], 'esto no es json')

    def test_video_progress_va_a_su_tabla(self):
        with patch(ENCOLAR) as encolar:
            self.client.post('/f/api/video-progress/', data=json.dumps({'email': 'x@y.com', 'percent': 10}),
                             content_type='application/json')
        self.assertEqual(encolar.call_args.args[0], 'video_progress')

    def test_no_captura_panel_ni_lecturas(self):
        with patch(ENCOLAR) as encolar:
            self.client.get('/f/api/lead/')
            self.client.post('/panel/algo/', data={})
            self.client.post('/admin/login/', data={})
        encolar.assert_not_called()

    def test_si_la_captura_falla_la_peticion_sigue(self):
        with patch.object(respaldo, 'capturar', side_effect=RuntimeError('boom')), \
                patch(ENCOLAR) as encolar, patch('calendario.leads.tasks.dispatch_lead_tasks'):
            resp = self.client.post('/f/api/lead/', data=json.dumps(_cuerpo()), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Lead.objects.exists())
        encolar.assert_not_called()

    def test_si_no_se_puede_encolar_la_peticion_sigue(self):
        with patch(ENCOLAR, side_effect=ConnectionError('redis caído')), \
                patch('calendario.leads.tasks.dispatch_lead_tasks'):
            resp = self.client.post('/f/api/lead/', data=json.dumps(_cuerpo()), content_type='application/json')
        self.assertEqual(resp.status_code, 200)


class ObjetoCompletoTest(TestCase):

    def test_datos_lleva_todos_los_campos_del_modelo(self):
        with patch('celery.app.task.Task.apply_async'):
            lead = Lead.objects.create(email='ana@ejemplo.com', full_name='Ana', utm_source='x')
        fila = respaldo.fila_de_objeto(lead, lead.created)
        nombres = {f.attname for f in Lead._meta.concrete_fields}
        self.assertEqual(nombres, set(fila['datos']) - {'tags'})
        self.assertEqual(fila['source_id'], lead.pk)
        self.assertEqual(fila['datos']['utm_source'], 'x')
        json.dumps(fila)  # serializable tal cual

    def test_el_lead_de_evento_tambien_se_respalda(self):
        with patch('calendario.leads.tasks.process_supabase') as sb, \
                patch('calendario.leads.tasks.process_neverbounce'), \
                patch('calendario.leads.tasks.process_crm_send'), \
                patch('calendario.leads.tasks.process_funnelchat'):
            Lead.objects.create(email='a@b.com', funnel='cb-lanzamiento11')
        self.assertTrue(sb.delay.called)

    def test_un_cambio_del_lead_reescribe_su_respaldo(self):
        with patch('celery.app.task.Task.apply_async'):
            lead = Lead.objects.create(email='a@b.com', funnel='cb-eu')
        with patch('calendario.leads.tasks.process_supabase') as sb, \
                self.captureOnCommitCallbacks(execute=True):
            lead.full_name = 'Otro'
            lead.save()
        sb.delay.assert_called_once_with(lead.pk)


@override_settings(SUPABASE_TABLE_REQUESTS='requests', SUPABASE_TABLE_VIDEO_PROGRESS='video_progress')
class SubidaDeRequestsTest(TestCase):

    def test_sube_a_la_tabla_que_toca_con_upsert_por_id(self):
        from calendario.core.tasks import process_request_supabase

        with patch('calendario.core.supabase.insert_rows') as insertar:
            process_request_supabase('video_progress', {'id': 'x'})
        insertar.assert_called_once_with('video_progress', [{'id': 'x'}], on_conflict='id')
