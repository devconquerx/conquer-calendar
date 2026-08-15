"""
La ventana reservable del cálculo de slots es la misma que pinta el calendario.

Dos reglas, las dos decididas en `EventType.ventana_reservas`:

  * Los dos modos son excluyentes: con un rango de fechas concreto el rolling
    `aviso_maximo_dias` no recorta nada (antes sí lo hacía, y un evento con
    rango del 13 al 18 y aviso máximo de 3 días se quedaba sin el día 18).
  * El corte del rolling es por día completo, no al minuto: con N días
    rodantes, el día hoy+N se abre entero a las 00:00 de ese día, en vez de
    ir destapando cada hora cuando el reloj llega a ella.

Se congela la hora ("hoy" es un lunes a las 16:00 de Madrid) porque justamente
lo que se comprueba es que la hora del día ya no influye en qué días se ofrecen.
"""
from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase

from calendario.availability.models import BloqueHorarioSemanal
from calendario.bookings.services import calcular_slots
from calendario.event_types.models import EventType
from tests.factories import crear_disponibilidad, crear_event_type, crear_host

PATCH_BUSY = 'calendario.bookings.services.obtener_busy_intervalos'
TZ = ZoneInfo('Europe/Madrid')

# Un lunes cualquiera en el futuro, para no depender del día en que se corra.
LUNES = date(2027, 3, 8)
AHORA = datetime.combine(LUNES, time(16, 0), tzinfo=TZ)


@patch(PATCH_BUSY, return_value=[])
@patch('django.utils.timezone.now', return_value=AHORA)
class VentanaDeSlotsTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='ventana.slots@test.com')
        # El host nace con los días abiertos de 00:00 a 23:59; aquí se comprueban
        # horas concretas, así que se deja un único horario L-V de 09:00 a 18:00.
        BloqueHorarioSemanal.objects.filter(host=self.host).delete()
        for dia in range(5):
            crear_disponibilidad(self.host, dia=dia)
        self.et = crear_event_type(self.host, nombre='Ventana test', duracion=30)

    def _horas(self, dia):
        """Horas locales (HH:MM) ofrecidas ese día."""
        slots = calcular_slots(self.et, dia, dia)
        return [s.astimezone(TZ).strftime('%H:%M') for s in slots]

    def _dias_con_horas(self, desde, hasta):
        slots = calcular_slots(self.et, desde, hasta)
        return sorted({s.astimezone(TZ).date() for s in slots})

    def _rolling(self, dias):
        self.et.aviso_maximo_dias = dias
        self.et.save(update_fields=['aviso_maximo_dias'])

    def _rango(self, inicio, fin):
        self.et.rango_tipo = EventType.RANGO_FECHAS
        self.et.rango_fecha_inicio = inicio
        self.et.rango_fecha_fin = fin
        self.et.save(update_fields=['rango_tipo', 'rango_fecha_inicio', 'rango_fecha_fin'])

    # --- rolling: el último día entra entero -----------------------------

    def test_el_ultimo_dia_rolling_se_abre_entero_desde_primera_hora(self, *_):
        """Son las 16:00 y el rolling es de 3 días: el jueves ya tiene las 09:00."""
        self._rolling(3)
        jueves = LUNES + timedelta(days=3)
        horas = self._horas(jueves)
        self.assertEqual(horas[0], '09:00')
        self.assertEqual(horas[-1], '17:30')

    def test_el_ultimo_dia_rolling_tiene_tantas_horas_como_uno_intermedio(self, *_):
        self._rolling(3)
        intermedio = LUNES + timedelta(days=2)
        ultimo = LUNES + timedelta(days=3)
        self.assertEqual(self._horas(ultimo), self._horas(intermedio))

    def test_el_dia_siguiente_al_rolling_sigue_cerrado(self, *_):
        self._rolling(3)
        self.assertEqual(self._horas(LUNES + timedelta(days=4)), [])

    def test_hoy_respeta_la_hora_actual(self, *_):
        """El corte por día es solo por arriba; hoy no se reserva hacia atrás."""
        self._rolling(3)
        horas = self._horas(LUNES)
        self.assertEqual(horas[0], '16:00')

    # --- rango de fechas: el rolling no pinta nada ------------------------

    def test_el_rango_de_fechas_ignora_un_aviso_maximo_mas_corto(self, *_):
        """El caso real: rango de 6 días con aviso máximo de 3."""
        self._rolling(3)
        self._rango(LUNES - timedelta(days=1), LUNES + timedelta(days=4))
        # El viernes (hoy+4) cae fuera del rolling pero dentro del rango.
        viernes = LUNES + timedelta(days=4)
        self.assertEqual(self._horas(viernes)[0], '09:00')

    def test_el_rango_de_fechas_manda_en_los_dos_extremos(self, *_):
        self._rolling(3)
        self._rango(LUNES + timedelta(days=1), LUNES + timedelta(days=4))
        dias = self._dias_con_horas(LUNES, LUNES + timedelta(days=10))
        self.assertEqual(dias, [LUNES + timedelta(days=n) for n in (1, 2, 3, 4)])
