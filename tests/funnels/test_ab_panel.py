"""El listado de tests A/B del panel no puede separarse del registro real.

El registro que manda vive en el front (`frontend/src/lib/formVariant.js`): es
el navegador quien asigna la variante. `calendario/funnels/ab_tests.py` es un
espejo en Python para poder pintarlo en /funnels/, y este test lee el fichero
JS y compara, de modo que añadir un experimento sin actualizar el panel —o al
revés— rompe la suite en vez de dejar el panel mintiendo en silencio.
"""
import re
from pathlib import Path

from django.test import TestCase

from calendario.funnels.ab_tests import TESTS_AB

JS = Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'lib' / 'formVariant.js'

# En el JS, el código de cada funnel se traduce al slug del FunnelForm; el panel
# usa el código corto con el que el CRM indexa (cb-latam, cl-eu…).
SLUG_A_CODIGO = {
    'blocks-latam': 'cb-latam', 'blocks-eu': 'cb-eu', 'blocks-eu-2': 'cb-eu-2', 'blocks-us': 'cb-us',
    'finance-latam': 'fi-latam', 'finance-eu': 'fi-eu', 'finance-us': 'fi-us',
    'languages-latam': 'cl-latam', 'languages-eu': 'cl-eu', 'languages-us': 'cl-us',
    'languages-ge': 'cl-ge', 'legal-eu': 'cg-eu',
}


def _experimentos_del_js():
    """(codigo_funnel, variantes) de cada experimento declarado en el front."""
    js = JS.read_text(encoding='utf-8')
    encontrados = []
    for bloque in re.findall(r"funnelSlug === '([a-z0-9-]+)'.*?variants: \[([^\]]+)\]", js, re.S):
        slug, variantes = bloque
        codigos = re.findall(r"'(\d+)'", variantes)
        encontrados.append((SLUG_A_CODIGO.get(slug, slug), tuple(codigos)))
    # Los experimentos de vídeo se declaran en una tabla plana, con el slug como
    # propiedad en vez de dentro del `match`.
    for slug, variantes in re.findall(r"funnelSlug: '([a-z0-9-]+)'.*?variants: \[([^\]]+)\]", js):
        codigos = re.findall(r"'(\d+)'", variantes)
        encontrados.append((SLUG_A_CODIGO.get(slug, slug), tuple(codigos)))
    return encontrados


class PanelDeTestsABTest(TestCase):

    def test_el_panel_lista_exactamente_los_experimentos_del_front(self):
        del_js = sorted(_experimentos_del_js())
        del_panel = sorted((funnel, (a[1], b[1])) for funnel, _, _, a, b in TESTS_AB)
        self.assertEqual(
            del_panel, del_js,
            'El panel /funnels/ y frontend/src/lib/formVariant.js se han separado. '
            'Actualiza calendario/funnels/ab_tests.py.',
        )

    def test_ningun_codigo_se_repite_entre_tests(self):
        codigos = [c for _, _, _, a, b in TESTS_AB for c in (a[1], b[1])]
        repetidos = {c for c in codigos if codigos.count(c) > 1}
        self.assertEqual(repetidos, set(), f'Códigos duplicados entre tests: {repetidos}')

    def test_el_panel_pinta_la_tabla(self):
        resp = self.client.get('/funnels/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Tests A/B activos', html)
        for funnel, _, prueba, a, b in TESTS_AB:
            self.assertIn(f'>{a[1]}</span>', html, f'falta el código {a[1]} de {funnel}')
            self.assertIn(f'>{b[1]}</span>', html, f'falta el código {b[1]} de {funnel}')
