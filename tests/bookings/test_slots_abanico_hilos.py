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
