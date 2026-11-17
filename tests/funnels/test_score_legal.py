# -*- coding: utf-8 -*-
"""Score de Conquer Legal con el formulario de la VSL de optimización fiscal.

Fórmula del equipo de Legal: (P4 + P5 + P6 + P7 + P8) / 5, redondeado a un
decimal, sin el país. Los casos salen de la tabla de equivalencias del PDF.
"""
from types import SimpleNamespace

from django.test import TestCase

from calendario.funnels.models import FunnelForm
from calendario.funnels.scoring import resolver_outcome

SL = 'Tengo una sociedad (SL o SA).'
AUTONOMO = 'Soy autónomo.'
EMPEZANDO = 'Todavía no tengo actividad (estoy empezando).'
VARIAS = 'Tengo varias sociedades.'

def respuestas(trabajo=SL, facturacion='Entre 250.000 € y 1.000.000 € al año.',
               socios='No, soy el único propietario.',
               ayuda='No, siempre me lo ha llevado mi gestor y nunca hemos revisado la estructura.',
               texto='x' * 150, pais='Spain'):
    return {
        'country': pais,
        'work_structure': trabajo,
        'annual_revenue': facturacion,
        'has_partners': socios,
        'prior_tax_help': ayuda,
        'tax_concerns': texto,
    }


class ScoreLegalTest(TestCase):

    def promedio(self, resp, key='LegalEu'):
        return resolver_outcome(FunnelForm.objects.get(key=key), resp)['promedio']

    def test_ejemplo_del_pdf_da_3_2(self):
        # SL (3) + 250k-1M (3) + sin socio (4) + gestor (3) + 150 caracteres (3) = 16 / 5
        self.assertEqual(self.promedio(respuestas()), 3.2)

    def test_legal_eu_2_puntua_igual(self):
        self.assertEqual(self.promedio(respuestas(), key='LegalEu2'), 3.2)

    def test_el_pais_no_cuenta(self):
        # Un país con 1 punto en la tabla global no mueve el score.
        self.assertEqual(self.promedio(respuestas(pais='Chad')), 3.2)

    def test_peor_lead_posible_1_4(self):
        resp = respuestas(trabajo=EMPEZANDO, facturacion='Menos de 100.000 € al año.',
                          socios='Sí, tengo uno o más socios.',
                          ayuda='Sí, y ya tengo una estructura optimizada.', texto='poco')
        self.assertEqual(self.promedio(resp), 1.4)

    def test_mejor_lead_posible_4_0(self):
        resp = respuestas(trabajo=VARIAS, facturacion='Más de 1.000.000 € al año.',
                          ayuda='Sí, pero no me dieron ninguna solución que funcionara.',
                          texto='x' * 250)
        self.assertEqual(self.promedio(resp), 4.0)

    def test_tramos_de_caracteres(self):
        # Base sin el texto: 3 + 3 + 4 + 3 = 13
        for largo, puntos in [(1, 1), (29, 1), (30, 2), (99, 2), (100, 3), (249, 3), (250, 4)]:
            with self.subTest(largo=largo):
                esperado = round((13 + puntos) / 5, 1)
                self.assertEqual(self.promedio(respuestas(texto='x' * largo)), esperado)

    def test_autonomo_suma_2(self):
        # 2 + 3 + 4 + 3 + 3 = 15 / 5
        self.assertEqual(self.promedio(respuestas(trabajo=AUTONOMO)), 3.0)

    def test_nadie_se_descalifica_por_score(self):
        resp = respuestas(trabajo=EMPEZANDO, facturacion='Menos de 100.000 € al año.',
                          socios='Sí, tengo uno o más socios.',
                          ayuda='Sí, y ya tengo una estructura optimizada.', texto='poco')
        outcome = resolver_outcome(FunnelForm.objects.get(key='LegalEu'), resp)
        self.assertNotIn(outcome.get('motivo'), ('validate', 'score_below_min'))

    def test_el_formulario_tiene_las_preguntas_en_orden(self):
        config = FunnelForm.objects.get(key='LegalEu').config
        self.assertEqual(config['q_order'], [
            'work_structure', 'annual_revenue', 'has_partners', 'prior_tax_help', 'tax_concerns',
        ])
        ids = [b['id'] for b in config['blocks']]
        self.assertEqual(ids[-5:], config['q_order'])
        for viejo in ('business_type', 'team_size', 'legal_goal', 'current_problems'):
            self.assertNotIn(viejo, ids)


class LosDemasFunnelsSiguenContandoElPaisTest(TestCase):

    def test_sin_la_opcion_el_pais_entra_en_la_media(self):
        funnel = SimpleNamespace(key='X', config={
            'q_order': ['work_structure'],
            'score_ranges': [{'min_score': 0, 'max_score': 100}],
        })
        # Chad (1) + sociedad (3) = 4 / 2
        resp = {'country': 'Chad', 'work_structure': SL}
        self.assertEqual(resolver_outcome(funnel, resp)['promedio'], 2.0)
