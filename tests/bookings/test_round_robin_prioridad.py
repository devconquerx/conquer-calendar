"""
Tests de la prioridad de organizadores en el reparto round-robin.

`EventTypeXHost.prioridad` va de 1 a 3, donde 3 es la más alta. El orden de
selección es: mayor prioridad -> menos reservas confirmadas -> orden de entrada
al pool. Como todos los organizadores nacen en la prioridad por defecto, mientras
nadie la toque el criterio es constante y el reparto se comporta exactamente como
antes de existir el campo.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase

from calendario.bookings.models import Reserva
from calendario.bookings.services import crear_reserva as svc_crear
from calendario.event_types.models import EventType, EventTypeXHost
from tests.factories import crear_disponibilidad, crear_host, slot_futuro


def _reservar(et, inicio, email):
    return svc_crear(
        event_type=et, inicio_utc=inicio,
        nombre_invitado='Lead', email_invitado=email,
    )


def _set_prioridad(et, host, valor):
    EventTypeXHost.objects.filter(event_type=et, host=host).update(prioridad=valor)


@patch('calendario.bookings.services.hay_conflicto_calendario', return_value=False)
@patch('calendario.bookings.services.crear_evento_google')
class PrioridadRoundRobinTest(TestCase):

    def setUp(self):
        # Tres organizadores con la misma disponibilidad: los tres compiten por
        # cada slot, así que el desempate lo decide siempre el algoritmo.
        self.a = crear_host(email='host.a@conquerx.com', first_name='Ana', last_name='A')
        self.b = crear_host(email='host.b@conquerx.com', first_name='Beto', last_name='B')
        self.c = crear_host(email='host.c@conquerx.com', first_name='Caro', last_name='C')
        for h in (self.a, self.b, self.c):
            for dia in range(5):
                crear_disponibilidad(h, dia=dia)

        self.et = EventType.objects.create(
            host=self.a, nombre='Evento de equipo', duracion_minutos=30,
            buffer_antes_minutos=0, buffer_despues_minutos=0,
            aviso_minimo_minutos=0, activo=True,
            unico_por_invitado=False,
        )
        # El orden de creación fija el pivot.id, que es el último desempate.
        for h in (self.a, self.b, self.c):
            EventTypeXHost.objects.create(event_type=self.et, host=h)

    def test_prioridad_por_defecto_es_uno(self, _ev, _conf):
        valores = list(
            EventTypeXHost.objects
            .filter(event_type=self.et)
            .values_list('prioridad', flat=True)
        )
        self.assertEqual(valores, [1, 1, 1])

    def test_sin_prioridad_reparte_como_siempre(self, _ev, _conf):
        # Todos en 1: gana el menos cargado y, a igualdad, el primero del pool.
        r1 = _reservar(self.et, slot_futuro(dias=1), 'x1@x.com')
        r2 = _reservar(self.et, slot_futuro(dias=2), 'x2@x.com')
        r3 = _reservar(self.et, slot_futuro(dias=3), 'x3@x.com')
        self.assertEqual([r1.host, r2.host, r3.host], [self.a, self.b, self.c])

    def test_la_prioridad_alta_gana_aunque_tenga_mas_carga(self, _ev, _conf):
        _set_prioridad(self.et, self.c, 3)
        # Caro arranca con carga y aun así se lleva las siguientes: la prioridad
        # se evalúa antes que el reparto por carga.
        for i in range(3):
            inicio = slot_futuro(dias=20 + i)
            Reserva.objects.create(
                event_type=self.et, host=self.c,
                inicio_utc=inicio,
                fin_utc=inicio + timedelta(minutes=30),
                nombre_invitado='Previa', email_invitado=f'prev{i}@x.com',
            )
        r1 = _reservar(self.et, slot_futuro(dias=1), 'x1@x.com')
        r2 = _reservar(self.et, slot_futuro(dias=2), 'x2@x.com')
        self.assertEqual(r1.host, self.c)
        self.assertEqual(r2.host, self.c)

    def test_entre_iguales_decide_la_carga(self, _ev, _conf):
        # Dos en prioridad 3 y uno en 1: el de prioridad baja nunca entra, y
        # entre los dos altos se alterna por carga.
        _set_prioridad(self.et, self.b, 3)
        _set_prioridad(self.et, self.c, 3)
        hosts = [
            _reservar(self.et, slot_futuro(dias=d), f'x{d}@x.com').host
            for d in (1, 2, 3, 4)
        ]
        self.assertNotIn(self.a, hosts)
        self.assertEqual(hosts, [self.b, self.c, self.b, self.c])

    def test_prioridad_intermedia_se_ordena_entre_las_otras(self, _ev, _conf):
        _set_prioridad(self.et, self.a, 1)
        _set_prioridad(self.et, self.b, 2)
        _set_prioridad(self.et, self.c, 3)
        r = _reservar(self.et, slot_futuro(dias=1), 'x1@x.com')
        self.assertEqual(r.host, self.c)
        # Si el de prioridad 3 deja de estar libre, hereda el de prioridad 2.
        EventTypeXHost.objects.filter(event_type=self.et, host=self.c).delete()
        r2 = _reservar(self.et, slot_futuro(dias=2), 'x2@x.com')
        self.assertEqual(r2.host, self.b)

    def test_bajar_la_prioridad_deja_al_host_de_ultimo(self, _ev, _conf):
        # Ana es la primera del pool, así que sin tocar nada ganaría el desempate.
        _set_prioridad(self.et, self.b, 2)
        _set_prioridad(self.et, self.c, 2)
        r = _reservar(self.et, slot_futuro(dias=1), 'x1@x.com')
        self.assertEqual(r.host, self.b)
