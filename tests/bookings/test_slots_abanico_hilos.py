"""
El calendario público no puede llevarse la base de datos por delante.

`calcular_slots` paraleliza el cálculo por organizador y cada hilo abre su PROPIA
conexión a Postgres. Mientras el abanico fue `len(hosts)` sin tope, una sola
visita a un evento de equipo grande —el pool de `1-on-1 | Conquer Languages`
tiene 19 personas— se llevaba 19 de las 47 conexiones que deja el plan
gestionado. Con tres visitas simultáneas, o dos durante un despliegue azul/verde,
Postgres empezaba a rechazar y el calendario devolvía un 500 justo en la página
de coger hora (FUNNELS-AM).
"""
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase

from calendario.availability.models import BloqueHorarioSemanal
from calendario.bookings import services
from calendario.bookings.services import _MAX_HILOS_SLOTS, calcular_slots
from calendario.event_types.models import EventTypeXHost
from tests.factories import crear_event_type, crear_host


class AbanicoDeHilosTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        BloqueHorarioSemanal.objects.filter(horario__host=self.host).delete()
        self.et = crear_event_type(self.host)

    def _poblar_pool(self, cuantos):
        """Añade `cuantos` organizadores al pool, además del dueño del evento."""
        for i in range(cuantos):
            otro = crear_host(email=f'host{i}@test.com', first_name=f'Host{i}')
            BloqueHorarioSemanal.objects.filter(horario__host=otro).delete()
            EventTypeXHost.objects.get_or_create(event_type=self.et, host=otro)

    def _max_workers_al_calcular(self):
        hoy = date.today()
        with patch.object(
            services, 'ThreadPoolExecutor', wraps=services.ThreadPoolExecutor
        ) as pool:
            calcular_slots(self.et, hoy, hoy + timedelta(days=7))
        pool.assert_called_once()
        return pool.call_args.kwargs['max_workers']

    def test_un_pool_grande_no_pasa_del_tope(self):
        self._poblar_pool(18)  # 19 en total: el pool real que tumbó el calendario
        self.assertEqual(self._max_workers_al_calcular(), _MAX_HILOS_SLOTS)

    def test_un_pool_pequeno_no_abre_hilos_de_mas(self):
        self._poblar_pool(1)  # 2 en total, por debajo del tope
        self.assertEqual(self._max_workers_al_calcular(), 2)

    def test_un_solo_host_no_abre_hilos(self):
        hoy = date.today()
        with patch.object(services, 'ThreadPoolExecutor') as pool:
            calcular_slots(self.et, hoy, hoy + timedelta(days=7))
        pool.assert_not_called()


class UnaConexionPorHiloTest(AbanicoDeHilosTest):
    """Cada hilo se queda con su conexión para todo su lote de organizadores.

    Se cerraba tras cada organizador, así que cada uno abría una conexión nueva
    contra la Postgres gestionada, y eso costaba más que sus consultas: con las
    25 personas de `1-on-1 | Conquer Languages`, 2,3 s el cálculo entero frente
    a ~1 s con una conexión por hilo.
    """

    def test_cierra_una_vez_por_hilo_y_no_por_organizador(self):
        self._poblar_pool(18)
        hoy = date.today()
        # `wraps` para que de verdad cierre: con un mock pelado las conexiones de
        # los hilos se quedan abiertas y la BD de test no se puede borrar.
        with patch.object(services.connections, 'close_all',
                          wraps=services.connections.close_all) as close_all, \
                patch.object(services, '_calcular_slots_para_host',
                             wraps=services._calcular_slots_para_host) as por_host:
            calcular_slots(self.et, hoy, hoy + timedelta(days=7))
        self.assertEqual(close_all.call_count, _MAX_HILOS_SLOTS)
        # Y ningún organizador se queda sin calcular por ir en lotes.
        self.assertEqual(
            sorted(c.args[1].pk for c in por_host.call_args_list),
            sorted(h.pk for h in services._obtener_hosts_pool(self.et)),
        )
