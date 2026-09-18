"""
El registro de fallos no puede fallar él también.

Caso real (FUNNELS-DQ/DT): una reserva se borra, la tarea que la mandaba al CRM
falla con `Reserva.DoesNotExist` y el registrador de fallos intenta guardar el
`TaskFailureLog` apuntando a esa reserva. La fila ya no está, así que Postgres
rechaza la clave ajena y el registro no se crea: el único sitio donde iba a
quedar constancia del fallo se cae por el mismo motivo que lo provocó.

Los dos FK del modelo ya son `null=True`, así que hay sitio para guardarlo sin
enlace. Lo que faltaba era no dar por hecho que la fila sigue ahí.
"""
from unittest.mock import Mock

from django.test import TransactionTestCase

from config.celery import _log_task_failure
from calendario.monitoring.models import TaskFailureLog


# Un id que no existe: la reserva se borró entre que la tarea se encoló y falló.
RESERVA_BORRADA = 28132


class FalloConObjetoBorradoTest(TransactionTestCase):
    """`TransactionTestCase` y no `TestCase` a propósito.

    Django declara sus claves ajenas DEFERRABLE INITIALLY DEFERRED, así que
    dentro de la transacción de un `TestCase` la comprobación se aplaza a un
    commit que nunca llega y el fallo NO se reproduce: el test pasaría en verde
    mientras producción sigue rompiéndose.
    """

    def _fallar(self, task_name, pk):
        _log_task_failure(
            task_name=task_name,
            task_id='una-tarea-cualquiera',
            exception=Exception('Reserva matching query does not exist.'),
            args=[pk],
            einfo=Mock(traceback=['Traceback...\n']),
        )

    def test_el_fallo_queda_registrado_aunque_la_reserva_ya_no_exista(self):
        self._fallar('calendario.bookings.tasks.process_schedule_crm', RESERVA_BORRADA)

        log = TaskFailureLog.objects.filter(
            task_name='calendario.bookings.tasks.process_schedule_crm',
        ).first()
        self.assertIsNotNone(
            log,
            'el fallo no se registró en ninguna parte: el IntegrityError del FK '
            'se llevó por delante el único rastro que iba a quedar',
        )
        self.assertIsNone(log.reserva_id, 'no puede enlazar una fila que no existe')

    def test_se_conserva_de_qué_objeto_hablaba(self):
        """Sin el enlace, el id tiene que quedar en el texto o no sirve de nada."""
        self._fallar('calendario.bookings.tasks.process_schedule_crm', RESERVA_BORRADA)

        log = TaskFailureLog.objects.first()
        self.assertIn(str(RESERVA_BORRADA), log.exception_message)
