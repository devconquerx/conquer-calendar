"""
La última fila del calendario público se completa con los primeros días del
mes siguiente, y esos días son reservables.

Antes, los días de relleno se pintaban siempre apagados: quien entraba a final
de mes tenía que pasar de mes para ver las horas de "pasado mañana". Ahora la
cola de la cuadrícula es clicable (si tiene slots y cae dentro de la ventana
reservable), mientras que los días de relleno del principio siguen apagados
—ahí el mes ya arranca en el día 1—.

Marzo de 2027 es el mes de prueba porque empieza en lunes y tiene 31 días: la
cuadrícula queda de 5 filas exactas y la cola es del 1 al 4 de abril (jueves,
viernes, sábado y domingo).
"""
from datetime import date, datetime, time
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.urls import reverse

from calendario.availability.models import BloqueHorarioSemanal
from tests.factories import crear_disponibilidad, crear_event_type, crear_host

PATCH_BUSY = 'calendario.bookings.services.obtener_busy_intervalos'
TZ = ZoneInfo('Europe/Madrid')

# Un miércoles de marzo de 2027, para que la ventana rodante por defecto
# (60 días) cubra de sobra la cola de abril.
AHORA = datetime.combine(date(2027, 3, 10), time(9, 0), tzinfo=TZ)


class _DatetimeFijo(datetime):
    """La vista pública saca el "hoy" del visitante con datetime.now(tz)."""

    @classmethod
    def now(cls, tz=None):
        return AHORA.astimezone(tz) if tz else AHORA


@patch(PATCH_BUSY, return_value=[])
@patch('calendario.bookings.views_public.datetime', _DatetimeFijo)
@patch('django.utils.timezone.now', return_value=AHORA)
class CuadriculaColaMesTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='cola.mes@test.com')
        self.host.timezone = 'Europe/Madrid'
        self.host.save(update_fields=['timezone'])
        BloqueHorarioSemanal.objects.filter(horario__host=self.host).delete()
        for dia in range(5):  # L-V de 09:00 a 18:00
            crear_disponibilidad(self.host, dia=dia)
        self.et = crear_event_type(self.host, nombre='Cola de mes', duracion=30)

    def _url(self, nombre):
        return reverse(f'public_booking:{nombre}', kwargs={
            'user_slug': self.host.slug,
            'event_type_slug': self.et.slug,
        })

    def _grid(self, mes='2027-03-01'):
        resp = self.client.get(self._url('booking_page'), {'mes': mes, 'tz': 'Europe/Madrid'})
        self.assertEqual(resp.status_code, 200)
        return {d['fecha']: d for semana in resp.context['cal_semanas'] for d in semana}

    def test_la_cuadricula_llega_hasta_completar_la_ultima_fila(self, *_):
        grid = self._grid()
        self.assertEqual(min(grid), date(2027, 3, 1))
        self.assertEqual(max(grid), date(2027, 4, 4))

    def test_la_cola_del_mes_siguiente_es_clicable(self, *_):
        grid = self._grid()
        self.assertTrue(grid[date(2027, 4, 1)]['clickable'])   # jueves
        self.assertTrue(grid[date(2027, 4, 2)]['clickable'])   # viernes
        self.assertFalse(grid[date(2027, 4, 3)]['clickable'])  # sábado, sin horario
        self.assertFalse(grid[date(2027, 4, 4)]['clickable'])  # domingo, sin horario

    def test_la_cola_sin_horas_se_pinta_apagada_pero_visible(self, *_):
        # El fin de semana de la cola no es reservable, pero tiene que verse:
        # 'out' lleva visibility:hidden y dejaría huecos en mitad de la fila.
        grid = self._grid()
        for dia in (1, 2, 3, 4):
            self.assertTrue(grid[date(2027, 4, dia)]['es_cola'])
        self.assertFalse(grid[date(2027, 3, 31)]['es_cola'])

    def test_la_cola_fuera_de_la_ventana_se_sigue_viendo(self, *_):
        # Aunque no haya nada reservable en el mes siguiente, la fila se
        # completa igual en vez de quedarse a medias.
        self.et.aviso_maximo_dias = 21  # 10/03 + 21 = 31/03
        self.et.save(update_fields=['aviso_maximo_dias'])
        grid = self._grid()
        for dia in (1, 2, 3, 4):
            celda = grid[date(2027, 4, dia)]
            self.assertTrue(celda['es_cola'])
            self.assertFalse(celda['clickable'])

    def test_el_relleno_del_principio_sigue_apagado(self, *_):
        # Abril de 2027 empieza en jueves: la primera fila arrastra del 29 al 31
        # de marzo, que son laborables con horas y aun así no se ofrecen.
        grid = self._grid(mes='2027-04-01')
        for dia in (29, 30, 31):
            celda = grid[date(2027, 3, dia)]
            self.assertFalse(celda['en_mes'])
            self.assertFalse(celda['es_cola'])
            self.assertFalse(celda['clickable'])

    def test_la_cola_respeta_el_final_de_la_ventana_reservable(self, *_):
        # Ventana rodante que muere el 31 de marzo: la cola de abril se apaga.
        self.et.aviso_maximo_dias = 21  # 10/03 + 21 = 31/03
        self.et.save(update_fields=['aviso_maximo_dias'])
        grid = self._grid()
        self.assertTrue(grid[date(2027, 3, 31)]['clickable'])
        self.assertFalse(grid[date(2027, 4, 1)]['clickable'])

    def test_el_json_del_mes_trae_los_slots_de_la_cola(self, *_):
        resp = self.client.get(self._url('slots_mes_json'), {'mes': '2027-03', 'tz': 'Europe/Madrid'})
        self.assertEqual(resp.status_code, 200)
        dias = resp.json()['dias']
        self.assertIn('2027-04-01', dias)
        self.assertIn('2027-04-02', dias)
        self.assertNotIn('2027-04-03', dias)
