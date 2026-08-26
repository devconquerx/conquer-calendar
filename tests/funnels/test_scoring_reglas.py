# -*- coding: utf-8 -*-
"""Cómo se combinan las reglas de `validate` y `neverCancel`.

No había ningún test sobre esto, y la semántica importa: son las reglas que
deciden si un lead pasa a llamada o se le cancela.

Entre reglas distintas es O —basta con que encaje una—. Dentro de una regla es
Y: la de Blocks US que cancela al desempleado lo hace solo si además está en
trámites, no a cualquiera de las dos cosas por separado.
"""
from django.test import TestCase

from calendario.funnels.scoring import aplica_never_cancel, aplica_validate


class ReglasDeUnaSolaClaveTest(TestCase):

    def test_encaja_cuando_la_respuesta_es_esa(self):
        reglas = [{'age': 'Soy menor de 18 años.'}]
        self.assertTrue(aplica_validate({'age': 'Soy menor de 18 años.'}, reglas))

    def test_y_no_cuando_es_otra(self):
        reglas = [{'age': 'Soy menor de 18 años.'}]
        self.assertFalse(aplica_validate({'age': 'Tengo entre 18 y 24 años.'}, reglas))

    def test_entre_reglas_basta_con_que_encaje_una(self):
        reglas = [{'age': 'Soy menor de 18 años.'},
                  {'income': 'Menos de 350 dólares mensuales.'}]
        respuestas = {'age': 'Tengo entre 25 y 34 años.',
                      'income': 'Menos de 350 dólares mensuales.'}
        self.assertTrue(aplica_validate(respuestas, reglas))


class ReglasDeVariasClavesTest(TestCase):
    """Dentro de una regla, todas las condiciones tienen que darse.

    Antes bastaba con una: la regla de Alex —desempleado Y en trámites— habría
    cancelado a todo el que estuviera en trámites aunque tuviera empleo, que es
    justo lo contrario de lo que pide.
    """

    REGLA = [{'employment_situation': 'Me encuentro desempleado.',
              'legal_status': 'Todavía estoy en trámites'}]

    def test_cancela_cuando_se_dan_las_dos(self):
        respuestas = {'employment_situation': 'Me encuentro desempleado.',
                      'legal_status': 'Todavía estoy en trámites'}
        self.assertTrue(aplica_validate(respuestas, self.REGLA))

    def test_no_cancela_al_desempleado_con_otra_residencia(self):
        respuestas = {'employment_situation': 'Me encuentro desempleado.',
                      'legal_status': 'Green card'}
        self.assertFalse(aplica_validate(respuestas, self.REGLA))

    def test_no_cancela_a_quien_esta_en_tramites_pero_trabaja(self):
        respuestas = {'employment_situation': 'Tengo un empleo.',
                      'legal_status': 'Todavía estoy en trámites'}
        self.assertFalse(aplica_validate(respuestas, self.REGLA))

    def test_lo_mismo_vale_para_never_cancel(self):
        regla = [{'legal_status': 'Green card', 'income': 'Más de 5000 dólares mensuales.'}]
        self.assertTrue(aplica_never_cancel(
            {'legal_status': 'Green card', 'income': 'Más de 5000 dólares mensuales.'}, regla))
        self.assertFalse(aplica_never_cancel(
            {'legal_status': 'Green card', 'income': 'Menos de 350 dólares mensuales.'}, regla))
