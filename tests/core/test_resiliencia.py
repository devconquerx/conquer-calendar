"""
Que un servicio caído nunca trabe la cola (incidente del 28-sep-2026).

ActiveCampaign empezó a dar timeouts, sus tareas ocuparon el único worker y los
sweeps, que cada minuto reencolaban todo lo que no tenía su tag *_done sin saber
que ya estaba en la cola, la llevaron a 115.000 tareas. Prellamadas y reservas
llegaron al CRM con horas de retraso y el monitor, atascado en la misma cola,
no avisó.

Cada bloque de tests cubre una de las vías por las que eso podía pasar. Usan el
Redis local (base 15, que se vacía en cada test) porque lo que se prueba son
precisamente los scripts atómicos que corren allí.
"""
from unittest.mock import MagicMock, patch

import redis
import requests
from celery import Task
from celery.exceptions import Ignore
from django.conf import settings
from django.test import TestCase, override_settings

from calendario.core import resiliencia
from config.celery import app

REDIS_TEST = settings.CELERY_BROKER_URL.rsplit('/', 1)[0] + '/15'


class ConRedis(TestCase):

    def setUp(self):
        self._anterior = resiliencia._cliente
        resiliencia._cliente = redis.Redis.from_url(REDIS_TEST, socket_timeout=1)
        resiliencia._cliente.flushdb()

    def tearDown(self):
        resiliencia._cliente.flushdb()
        resiliencia._cliente = self._anterior


def _error_http(codigo, retry_after=None):
    resp = requests.Response()
    resp.status_code = codigo
    if retry_after:
        resp.headers['Retry-After'] = str(retry_after)
    return requests.HTTPError(f'{codigo}', response=resp)


class UnaCopiaPendienteTest(ConRedis):
    """El motor de la avalancha: encolar lo que ya estaba en la cola."""

    def test_la_segunda_copia_no_se_encola(self):
        self.assertTrue(resiliencia.reservar_pendiente('t', (1,), {}))
        self.assertFalse(resiliencia.reservar_pendiente('t', (1,), {}))
        self.assertTrue(resiliencia.reservar_pendiente('t', (2,), {}))

    def test_al_empezar_la_tarea_se_puede_volver_a_encolar(self):
        resiliencia.reservar_pendiente('t', (1,), {})
        resiliencia.soltar_pendiente('t', (1,), {})
        self.assertTrue(resiliencia.reservar_pendiente('t', (1,), {}))

    def test_apply_async_no_publica_duplicados_pero_si_reintentos(self):
        from calendario.leads.tasks import process_supabase

        with patch.object(Task, 'apply_async') as publicar:
            process_supabase.delay(7)
            process_supabase.delay(7)
            process_supabase.apply_async((7,), retries=1, countdown=5)
        self.assertEqual(publicar.call_count, 2)  # la primera + el reintento

    def test_dos_sweeps_seguidos_no_duplican_nada(self):
        """El incidente, reproducido: leads sin sus tags *_done y el sweep
        corriendo cada minuto mientras la cola no avanza."""
        from datetime import timedelta
        from django.utils import timezone
        from calendario.leads.models import Lead
        from calendario.leads.tasks import sweep_incomplete_leads

        with patch.object(Task, 'apply_async') as publicar:
            for i in range(3):
                lead = Lead.objects.create(email=f'lead{i}@ejemplo.com')
                Lead.objects.filter(pk=lead.pk).update(created=timezone.now() - timedelta(minutes=30))
            resiliencia._cliente.flushdb()  # lo que encoló el alta ya "se perdió"
            publicar.reset_mock()

            primera = sweep_incomplete_leads()
            publicadas = publicar.call_count
            segunda = sweep_incomplete_leads()

        self.assertGreater(primera, 0)
        self.assertGreater(publicadas, 0)
        self.assertEqual(publicar.call_count, publicadas, 'el segundo sweep no debe publicar nada')
        self.assertGreaterEqual(segunda, 0)


class HuecosPorServicioTest(ConRedis):
    """Un servicio lento no puede quedarse con todos los procesos del worker."""

    def test_no_pasa_de_sus_huecos(self):
        topes = resiliencia.SERVICIOS['activecampaign']['huecos']
        for i in range(topes):
            self.assertTrue(resiliencia.ocupar_hueco('activecampaign', f'id{i}'))
        self.assertFalse(resiliencia.ocupar_hueco('activecampaign', 'otro'))
        # Otro servicio no se entera.
        self.assertTrue(resiliencia.ocupar_hueco('meta', 'x'))

    def test_al_soltar_queda_libre(self):
        topes = resiliencia.SERVICIOS['activecampaign']['huecos']
        for i in range(topes):
            resiliencia.ocupar_hueco('activecampaign', f'id{i}')
        resiliencia.soltar_hueco('activecampaign', 'id0')
        self.assertTrue(resiliencia.ocupar_hueco('activecampaign', 'nuevo'))

    def test_un_hueco_de_un_worker_muerto_caduca(self):
        topes = resiliencia.SERVICIOS['activecampaign']['huecos']
        antes = resiliencia.time.time() - resiliencia.TTL_HUECO - 1
        with patch.object(resiliencia.time, 'time', return_value=antes):
            for i in range(topes):
                resiliencia.ocupar_hueco('activecampaign', f'muerto{i}')
        self.assertTrue(resiliencia.ocupar_hueco('activecampaign', 'vivo'))


class RitmoPorServicioTest(ConRedis):

    def test_respeta_el_ritmo_con_su_rafaga(self):
        with patch.dict(resiliencia.SERVICIOS, {'prueba': {'huecos': 10, 'por_min': 60}}):
            rafaga = 5  # 60/min → 1/s, 5 s de ráfaga
            for _ in range(rafaga):
                self.assertEqual(resiliencia.tomar_turno('prueba'), 0)
            espera = resiliencia.tomar_turno('prueba')
        self.assertGreater(espera, 0)
        self.assertLessEqual(espera, 1.01)

    def test_cada_tarea_reserva_su_turno_y_vuelven_espaciadas(self):
        """Sin tropel: la sexta espera 1 s, la séptima 2 s, la octava 3 s."""
        with patch.dict(resiliencia.SERVICIOS, {'prueba': {'huecos': 10, 'por_min': 60}}):
            esperas = [resiliencia.motivo_para_aplazar('prueba', f't{i}') for i in range(8)]
        self.assertEqual(esperas[:5], [None] * 5)
        segundos = [e[0] for e in esperas[5:]]
        for esperado, real in zip((1, 2, 3), segundos):
            self.assertAlmostEqual(real, esperado, delta=0.1)

    def test_al_llegar_su_turno_no_vuelve_a_la_cola(self):
        with patch.dict(resiliencia.SERVICIOS, {'prueba': {'huecos': 10, 'por_min': 60}}):
            for i in range(5):
                resiliencia.motivo_para_aplazar('prueba', f'r{i}')
            segundos, _ = resiliencia.motivo_para_aplazar('prueba', 'yo')
            despues = resiliencia.time.time() + segundos + 0.1
            with patch.object(resiliencia.time, 'time', return_value=despues):
                self.assertIsNone(resiliencia.motivo_para_aplazar('prueba', 'yo'))

    def test_con_el_circuito_abierto_pierde_el_turno(self):
        """Si conservara un turno vencido, al cerrarse saldrían todas a la vez."""
        resiliencia._reservar('yo', resiliencia.time.time() - 10)
        resiliencia.abrir_circuito('activecampaign', 30, 'prueba')
        resiliencia.motivo_para_aplazar('activecampaign', 'yo')
        self.assertIsNone(resiliencia._turno_reservado('yo'))

    def test_verificador_de_email_lee_su_variable_de_entorno(self):
        self.assertEqual(resiliencia._por_minuto('6/m', 0), 6)
        self.assertEqual(resiliencia._por_minuto('1/s', 0), 60)
        self.assertEqual(resiliencia._por_minuto('basura', 6), 6)


class CortacircuitosTest(ConRedis):

    def test_se_abre_tras_varios_fallos_de_red(self):
        for _ in range(resiliencia.FALLOS_PARA_ABRIR):
            resiliencia.registrar_fallo('activecampaign', requests.exceptions.ReadTimeout('lento'))
        self.assertGreater(resiliencia.circuito_abierto('activecampaign'), 0)
        self.assertEqual(resiliencia.circuito_abierto('meta'), 0)

    def test_un_429_lo_abre_al_momento_con_su_retry_after(self):
        resiliencia.registrar_fallo('activecampaign', _error_http(429, retry_after=120))
        self.assertGreater(resiliencia.circuito_abierto('activecampaign'), 100)

    def test_los_fallos_nuestros_no_cuentan(self):
        for _ in range(20):
            resiliencia.registrar_fallo('activecampaign', ValueError('dato malo'))
            resiliencia.registrar_fallo('activecampaign', _error_http(400))
        self.assertEqual(resiliencia.circuito_abierto('activecampaign'), 0)

    def test_un_exito_limpia_los_fallos(self):
        for _ in range(resiliencia.FALLOS_PARA_ABRIR - 1):
            resiliencia.registrar_fallo('activecampaign', requests.exceptions.ConnectionError())
        resiliencia.registrar_exito('activecampaign')
        resiliencia.registrar_fallo('activecampaign', requests.exceptions.ConnectionError())
        self.assertEqual(resiliencia.circuito_abierto('activecampaign'), 0)


def _tarea_real(nombre):
    """`shared_task` devuelve un proxy: para parchear su clase hace falta la tarea."""
    app.loader.import_default_modules()
    return app.tasks[nombre]


class AplazarEnVezDeEsperarTest(ConRedis):
    """Lo que no puede ejecutarse se reencola con retraso y libera el worker al
    instante: ni ocupa un proceso esperando ni gasta un reintento."""

    def _ejecutar_en_worker(self, tarea, *args):
        tarea.push_request(id='tarea-1', called_directly=False, is_eager=False, retries=0,
                           delivery_info={'exchange': '', 'routing_key': 'celery'})
        try:
            return tarea(*args)
        finally:
            tarea.pop_request()

    def test_con_el_circuito_abierto_se_aplaza_sin_ejecutar(self):
        process_activecampaign = _tarea_real('calendario.leads.tasks.process_activecampaign')

        resiliencia.abrir_circuito('activecampaign', 60, 'prueba')
        firma = MagicMock()
        with patch.object(type(process_activecampaign), 'signature_from_request', return_value=firma) as sfr, \
                patch.object(process_activecampaign, 'run') as run:
            with self.assertRaises(Ignore):
                self._ejecutar_en_worker(process_activecampaign, 1)
        run.assert_not_called()
        firma.apply_async.assert_called_once()
        self.assertEqual(sfr.call_args.kwargs['retries'], 0)  # no gasta reintento
        self.assertGreaterEqual(sfr.call_args.kwargs['countdown'], 1)
        self.assertLessEqual(sfr.call_args.kwargs['countdown'], resiliencia.APLAZO_MAX)

    def test_sin_huecos_se_aplaza(self):
        process_activecampaign = _tarea_real('calendario.leads.tasks.process_activecampaign')

        for i in range(resiliencia.SERVICIOS['activecampaign']['huecos']):
            resiliencia.ocupar_hueco('activecampaign', f'ocupado{i}')
        with patch.object(type(process_activecampaign), 'signature_from_request', return_value=MagicMock()), \
                patch.object(process_activecampaign, 'run') as run:
            with self.assertRaises(Ignore):
                self._ejecutar_en_worker(process_activecampaign, 1)
        run.assert_not_called()

    def test_si_puede_se_ejecuta_y_suelta_su_hueco(self):
        process_activecampaign = _tarea_real('calendario.leads.tasks.process_activecampaign')

        with patch.object(process_activecampaign, 'run', return_value='ok') as run:
            self.assertEqual(self._ejecutar_en_worker(process_activecampaign, 1), 'ok')
        run.assert_called_once()
        self.assertEqual(resiliencia.cliente().zcard('resiliencia:huecos:activecampaign'), 0)


class RedisCaidoTest(TestCase):
    """Si Redis no contesta, la protección se aparta: nunca bloquea por sí misma."""

    def setUp(self):
        self._anterior = resiliencia._cliente
        resiliencia._cliente = redis.Redis(host='127.0.0.1', port=1, socket_timeout=0.2,
                                           socket_connect_timeout=0.2)

    def tearDown(self):
        resiliencia._cliente = self._anterior

    def test_todo_se_abre(self):
        self.assertTrue(resiliencia.reservar_pendiente('t', (1,), {}))
        self.assertTrue(resiliencia.ocupar_hueco('activecampaign', 'x'))
        self.assertEqual(resiliencia.tomar_turno('activecampaign'), 0)
        self.assertEqual(resiliencia.circuito_abierto('activecampaign'), 0)
        self.assertIsNone(resiliencia.motivo_para_aplazar('activecampaign', 'x'))
        resiliencia.registrar_fallo('activecampaign', requests.exceptions.ReadTimeout())

    @patch('calendario.leads.tasks.dispatch_lead_tasks', side_effect=ConnectionError('redis caído'))
    def test_el_alta_de_lead_no_revienta(self, _):
        from calendario.leads.models import Lead
        Lead.objects.create(email='sigue@ejemplo.com')
        self.assertTrue(Lead.objects.filter(email='sigue@ejemplo.com').exists())


class ColasSeparadasTest(TestCase):
    """Lo del CRM y el monitor nunca comparten cola con marketing."""

    def _cola(self, nombre):
        return app.amqp.router.route({}, nombre, (), {})['queue'].name

    def test_rutas(self):
        self.assertEqual(self._cola('calendario.funnels.tasks.process_pre_schedule_crm'), 'crm')
        self.assertEqual(self._cola('calendario.bookings.tasks.process_schedule_crm'), 'crm')
        self.assertEqual(self._cola('calendario.leads.tasks.process_crm_send'), 'crm')
        self.assertEqual(self._cola('calendario.leads.tasks.sweep_incomplete_leads'), 'sistema')
        self.assertEqual(self._cola('calendario.monitoring.tasks.check_colas'), 'sistema')
        self.assertEqual(self._cola('calendario.leads.tasks.process_activecampaign'), 'celery')

    def test_toda_tarea_de_servicio_existe(self):
        """Un nombre mal escrito en el mapa dejaría esa tarea sin protección."""
        app.loader.import_default_modules()
        for nombre in list(resiliencia.SERVICIO_DE_TAREA) + list(resiliencia.RUTAS):
            self.assertIn(nombre, app.tasks, nombre)


@override_settings(MONITORING_ENABLED=False, CRM_INGEST_ENABLED=False)
class CheckColasTest(ConRedis):

    def test_avisa_de_cola_llena_y_circuito_abierto(self):
        from calendario.monitoring.tasks import check_colas

        resiliencia.abrir_circuito('activecampaign', 60, 'prueba')
        with patch.object(resiliencia, 'longitudes_de_colas', return_value={'celery': 99999, 'crm': 0, 'sistema': 0}):
            self.assertEqual(check_colas(), 2)

    @override_settings(MONITORING_HEARTBEAT_URL='https://hc.example/ping')
    def test_heartbeat(self):
        from calendario.monitoring.tasks import check_colas

        with patch.object(resiliencia, 'longitudes_de_colas', return_value={'celery': 0, 'crm': 0, 'sistema': 0}), \
                patch('requests.get') as get:
            check_colas()
        get.assert_called_once_with('https://hc.example/ping', timeout=5)


class TodaTareaClasificadaTest(TestCase):
    """Una tarea nueva sin clasificar se quedaría sin tope de huecos ni ritmo."""

    def test_toda_tarea_del_proyecto_esta_en_un_servicio_o_marcada_sin_servicio(self):
        app.loader.import_default_modules()
        propias = {n for n in app.tasks if n.startswith('calendario.')}
        sin_clasificar = propias - set(resiliencia.SERVICIO_DE_TAREA) - resiliencia.SIN_SERVICIO
        self.assertFalse(sin_clasificar, f'Clasifica en calendario/core/resiliencia.py: {sorted(sin_clasificar)}')


class CarrilDeRecuperacionTest(ConRedis):
    """Un backlog nunca retrasa a lo nuevo: lo que reencola un sweep solo usa la
    capacidad que el tráfico en vivo deja libre."""

    def test_con_la_fila_larga_la_recuperacion_cede_el_paso(self):
        with patch.dict(resiliencia.SERVICIOS, {'prueba': {'huecos': 10, 'por_min': 60}}):
            for i in range(40):  # tráfico en vivo: la fila va ~35 s por delante
                resiliencia.motivo_para_aplazar('prueba', f'vivo{i}')
            segundos, motivo = resiliencia.motivo_para_aplazar(
                'prueba', 'viejo', carril=resiliencia.CARRIL_RECUPERACION)
            self.assertTrue(motivo.startswith('cede'))
            self.assertGreaterEqual(segundos, resiliencia.CEDER_PASO[0])
            self.assertIsNone(resiliencia._turno_reservado('viejo'))  # no reservó
            # Lo nuevo sigue cogiendo turno detrás de la fila en vivo, no del backlog.
            espera_nueva, _ = resiliencia.motivo_para_aplazar('prueba', 'nuevo')
        self.assertLess(espera_nueva, 40)

    def test_con_la_fila_libre_la_recuperacion_pasa(self):
        with patch.dict(resiliencia.SERVICIOS, {'prueba': {'huecos': 10, 'por_min': 60}}):
            self.assertIsNone(resiliencia.motivo_para_aplazar(
                'prueba', 'viejo', carril=resiliencia.CARRIL_RECUPERACION))

    def test_lo_que_encola_un_sweep_lleva_el_carril(self):
        from calendario.leads.tasks import process_supabase

        with patch.object(Task, 'apply_async') as publicar:
            with resiliencia.en_carril(resiliencia.CARRIL_RECUPERACION):
                process_supabase.delay(1)
            process_supabase.delay(2)
        con_carril, sin_carril = publicar.call_args_list
        self.assertEqual(con_carril.kwargs['headers'], {'carril': 'recuperacion'})
        self.assertNotIn('headers', sin_carril.kwargs)


class MarcasHuerfanasTest(ConRedis):
    """Tras purgar una cola a mano, las marcas de pendiente no pueden bloquear
    al sweep durante horas."""

    def _mensaje(self, id_tarea):
        import json
        return json.dumps({'headers': {'id': id_tarea, 'task': 't'}, 'body': ''})

    def test_borra_las_que_apuntan_a_un_mensaje_que_ya_no_esta(self):
        r = resiliencia.cliente()
        antes = resiliencia.time.time() - 600
        with patch.object(resiliencia.time, 'time', return_value=antes):
            resiliencia.reservar_pendiente('t', (1,), {}, 'purgada')
            resiliencia.reservar_pendiente('t', (2,), {}, 'en-cola')
            resiliencia.reservar_pendiente('t', (3,), {}, 'aplazada')
        r.lpush('celery', self._mensaje('en-cola'))
        r.hset('unacked', 'tag1', '[%s, "", "celery"]' % self._mensaje('aplazada'))

        self.assertEqual(resiliencia.limpiar_pendientes_huerfanas(), 1)
        self.assertTrue(resiliencia.reservar_pendiente('t', (1,), {}))
        self.assertFalse(resiliencia.reservar_pendiente('t', (2,), {}))
        self.assertFalse(resiliencia.reservar_pendiente('t', (3,), {}))

    def test_respeta_las_recien_puestas(self):
        """Entre reservar la marca y publicar el mensaje pasan milisegundos."""
        resiliencia.reservar_pendiente('t', (1,), {}, 'aun-publicandose')
        self.assertEqual(resiliencia.limpiar_pendientes_huerfanas(), 0)

    def test_comando_todas(self):
        from io import StringIO
        from django.core.management import call_command

        resiliencia.reservar_pendiente('t', (1,), {}, 'x')
        call_command('limpiar_pendientes', '--todas', stdout=StringIO())
        self.assertTrue(resiliencia.reservar_pendiente('t', (1,), {}))


class HuecoDeTareaLargaTest(ConRedis):

    def test_una_tarea_de_una_hora_conserva_su_hueco(self):
        """sincronizar_bunny_r2 dura hasta 1 h: su hueco no puede caducar a los 2 min."""
        self.assertTrue(resiliencia.ocupar_hueco('bunny', 'larga', ttl=3630))
        despues = resiliencia.time.time() + 600
        with patch.object(resiliencia.time, 'time', return_value=despues):
            self.assertFalse(resiliencia.ocupar_hueco('bunny', 'otra'))


@override_settings(MONITORING_ENABLED=False, CRM_INGEST_ENABLED=False)
class SaludYMemoriaTest(ConRedis):

    def test_health_colas_da_503_sin_latido_y_200_con_latido_limpio(self):
        self.assertEqual(self.client.get('/health/colas/').status_code, 503)
        resiliencia.registrar_latido([])
        self.assertEqual(self.client.get('/health/colas/').status_code, 200)
        resiliencia.registrar_latido([('x', 'algo va mal')])
        self.assertEqual(self.client.get('/health/colas/').status_code, 503)

    def test_latido_viejo_da_503(self):
        resiliencia.registrar_latido([])
        with patch('time.time', return_value=resiliencia.time.time() + 600):
            self.assertEqual(self.client.get('/health/colas/').status_code, 503)

    @override_settings(MONITORING_REDIS_MAX_MB=1)
    def test_avisa_de_redis_lleno(self):
        from calendario.monitoring.tasks import check_colas

        with patch.object(resiliencia, 'longitudes_de_colas', return_value={'celery': 0, 'crm': 0, 'sistema': 0}), \
                patch.object(resiliencia, 'memoria_redis_mb', return_value=(900, 0)):
            self.assertEqual(check_colas(), 1)
