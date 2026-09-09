"""
El `journey_id` no puede llegar con la query string pegada detrás.

Los identificadores viajan de etapa a etapa por la URL y `journey_id` va siempre
el último. Cuando alguien vuelve al funnel desde un anuncio, Facebook añade su
`?fbclid=…` al final de la URL entera y acaba dentro del valor del último
parámetro. En producción se vieron `journey_id` de 237 caracteres para un
identificador que mide 24.

El daño era doble: la columna lo recortaba a 120 y el CRM rechazaba la
prellamada entera con un 400 contra su `varchar(100)`, perdiéndola
(FUNNELS-7T); y aunque hubiera cabido, `journey_id` es la clave del upsert del
CRM, así que un valor contaminado rompe la trazabilidad de esa persona.
"""
from django.test import TestCase

from calendario.funnels.views import _sanea_id


# El valor real de la prellamada 20014, recortado.
JOURNEY_CONTAMINADO = (
    'jrn_1788885337291_tvn8i8?fbclid=IwVERFWAUNGOZwZG9mBWZkaWQWUOA1FncpGP4'
    'kWbgJf5Y7QDJcN7Z-RWV4dG4DYWVtATAAYWRpZAGrNbptedS1c3J0YwZhcHBf'
)
JOURNEY_LIMPIO = 'jrn_1788885337291_tvn8i8'


class SaneaIdTest(TestCase):

    def test_quita_el_fbclid_que_facebook_pega_detras(self):
        self.assertEqual(_sanea_id(JOURNEY_CONTAMINADO), JOURNEY_LIMPIO)

    def test_el_resultado_cabe_en_la_columna_del_crm(self):
        # El CRM guarda journey_id en un varchar(100); el original medía 237.
        self.assertGreater(len(JOURNEY_CONTAMINADO), 100)
        self.assertLessEqual(len(_sanea_id(JOURNEY_CONTAMINADO)), 100)

    def test_corta_tambien_por_ampersand_y_almohadilla(self):
        self.assertEqual(_sanea_id('jrn_123_abc&utm_source=fb'), 'jrn_123_abc')
        self.assertEqual(_sanea_id('jrn_123_abc#seccion'), 'jrn_123_abc')

    def test_un_identificador_limpio_no_se_toca(self):
        # Lo normal es que no haya nada que limpiar; no debe alterarse.
        self.assertEqual(_sanea_id(JOURNEY_LIMPIO), JOURNEY_LIMPIO)
        self.assertEqual(_sanea_id('1788885337291_00v86z'), '1788885337291_00v86z')

    def test_recorta_los_espacios_como_hacia_el_strip_anterior(self):
        self.assertEqual(_sanea_id('  jrn_123_abc  '), 'jrn_123_abc')

    def test_los_vacios_no_revientan(self):
        self.assertEqual(_sanea_id(None), '')
        self.assertEqual(_sanea_id(''), '')
