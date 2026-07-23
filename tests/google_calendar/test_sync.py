from django.test import SimpleTestCase

from calendario.google_calendar.sync import _parse_evento


def _item(**extra):
    """Item mínimo de events.list con hora concreta."""
    base = {
        'id': 'evt1',
        'summary': 'Clase Formación Elite Viernes',
        'start': {'dateTime': '2026-07-31T18:30:00+02:00'},
        'end': {'dateTime': '2026-07-31T19:30:00+02:00'},
    }
    base.update(extra)
    return base


class ParseEventoDeclinadoTest(SimpleTestCase):
    """
    Un evento que el host rechazó no ocupa su agenda: freebusy de Google no lo
    cuenta, así que la copia local tampoco debe hacerlo (si no, bloquea slots
    que en realidad están libres).
    """

    def test_host_declino_marca_transparent(self):
        campos = _parse_evento(_item(attendees=[
            {'email': 'jordi@conquerfinance.com', 'self': True, 'responseStatus': 'declined'},
        ]))

        self.assertEqual(campos['transparencia'], 'transparent')

    def test_host_acepto_sigue_opaque(self):
        campos = _parse_evento(_item(attendees=[
            {'email': 'jordi@conquerfinance.com', 'self': True, 'responseStatus': 'accepted'},
        ]))

        self.assertEqual(campos['transparencia'], 'opaque')

    def test_otro_invitado_declino_no_afecta(self):
        """Solo cuenta el attendee `self`; que otro rechace no libera al host."""
        campos = _parse_evento(_item(attendees=[
            {'email': 'jordi@conquerfinance.com', 'self': True, 'responseStatus': 'accepted'},
            {'email': 'otro@conquerfinance.com', 'responseStatus': 'declined'},
        ]))

        self.assertEqual(campos['transparencia'], 'opaque')

    def test_sin_attendees_sigue_opaque(self):
        """Evento propio sin invitados: no hay respuesta que mirar."""
        campos = _parse_evento(_item())

        self.assertEqual(campos['transparencia'], 'opaque')

    def test_declinado_sin_responder_sigue_opaque(self):
        """needsAction/tentative no liberan el horario, igual que en freebusy."""
        for estado in ('needsAction', 'tentative'):
            with self.subTest(responseStatus=estado):
                campos = _parse_evento(_item(attendees=[
                    {'email': 'jordi@conquerfinance.com', 'self': True, 'responseStatus': estado},
                ]))

                self.assertEqual(campos['transparencia'], 'opaque')

    def test_declinado_en_evento_de_dia_completo(self):
        campos = _parse_evento({
            'id': 'evt2',
            'summary': 'Vacaciones equipo',
            'start': {'date': '2026-07-31'},
            'end': {'date': '2026-08-01'},
            'attendees': [{'self': True, 'responseStatus': 'declined'}],
        })

        self.assertEqual(campos['transparencia'], 'transparent')
        self.assertTrue(campos['es_todo_el_dia'])

    def test_cancelado_conserva_su_transparencia(self):
        """
        Un cancelado llega sin start/end y debe seguir devolviendo los campos
        mínimos para que _upsert_evento lo borre de la copia local.
        """
        campos = _parse_evento({
            'id': 'evt3',
            'status': 'cancelled',
            'attendees': [{'self': True, 'responseStatus': 'declined'}],
        })

        self.assertEqual(campos['estado'], 'cancelled')
        self.assertIsNone(campos['inicio_utc'])
