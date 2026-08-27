"""
El banner empaquetado para las páginas que no sirve Django.

`/f/conquerx-cookies.js` devuelve el mismo banner que ven las páginas de Django
—mismos estilos, mismo marcado, mismo comportamiento— en un fichero que Webflow
carga con una línea. Lo que se fija aquí es lo que no puede romperse sin que
alguien lo note tarde: que la región siga decidiendo el modelo legal, que la
marca salga del dominio, y que la respuesta no se pueda cachear.
"""
from django.test import TestCase
from django.urls import reverse


class BundleConsentimientoTest(TestCase):

    def _get(self, pais='ES', host='www.conquerblocks.com', **params):
        return self.client.get(
            reverse('funnels:conquerx_cookies_js'),
            params,
            HTTP_X_VISITOR_COUNTRY=pais,
            HTTP_HOST=host,
        )

    def _cuerpo(self, **kwargs):
        return self._get(**kwargs).content.decode('utf-8')

    def test_se_sirve_como_javascript_y_sin_caché(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertIn('javascript', resp['Content-Type'])
        # Depende del país del visitante: una caché compartida serviría el
        # banner bloqueante de un europeo a alguien de Lima.
        self.assertIn('no-store', resp['Cache-Control'])

    def test_en_europa_pide_permiso_antes(self):
        cuerpo = self._cuerpo(pais='ES')
        self.assertIn('var explicito = true', cuerpo)
        self.assertIn('Rechazar', cuerpo)

    def test_en_latam_informa_pero_no_bloquea(self):
        cuerpo = self._cuerpo(pais='MX')
        self.assertIn('var explicito = false', cuerpo)
        self.assertNotIn('Rechazar', cuerpo)

    def test_brasil_va_con_europa(self):
        """LGPD también es de consentimiento previo."""
        self.assertIn('var explicito = true', self._cuerpo(pais='BR'))

    def test_sin_país_conocido_se_pide_permiso(self):
        """Ante la duda, preguntar. Equivocarse al revés sería medir sin permiso."""
        self.assertIn('var explicito = true', self._cuerpo(pais='XX'))

    def test_la_marca_sale_del_dominio(self):
        # El acento viaja dentro de una cadena JS, así que `-` y `<` van
        # escapados: se busca el color, que no lo está.
        self.assertIn('#ff4000', self._cuerpo(host='www.conquerblocks.com'))
        self.assertIn('#15b961', self._cuerpo(host='www.conquerlanguages.com'))

    def test_la_corporativa_tiene_su_propia_paleta(self):
        """conquerx.com no es una escuela y no comparte su lenguaje visual: sin
        textura de cartón y sin el CTA pixelado. Los valores salen del botón
        «Contacto» de la propia página."""
        cuerpo = self._cuerpo(host='www.conquerx.com')
        self.assertIn('#333333', cuerpo)
        self.assertIn('Funnel Display', cuerpo)
        # `papel` y `pixel` son los que meten la textura y el recorte; sin ellos
        # esos bloques de CSS no se renderizan.
        self.assertNotIn('paperboard-texture', cuerpo)
        self.assertNotIn('clip-path:var(--pixel-clip)', cuerpo.replace('\\u002D', '-'))

    def test_un_dominio_desconocido_no_revienta(self):
        resp = self._get(host='loquesea.com')
        self.assertEqual(resp.status_code, 200)

    def test_la_marca_se_puede_forzar_por_query(self):
        cuerpo = self._cuerpo(host='loquesea.com', marca='conquer-languages')
        self.assertIn('#15b961', cuerpo)

    def test_el_comportamiento_va_incrustado(self):
        """Sin segunda petición: un fallo ahí dejaría el diálogo pintado y muerto."""
        cuerpo = self._cuerpo()
        self.assertIn("var COOKIE = 'cqx_consent'", cuerpo)
        self.assertNotIn('static/js/consentimiento.js', cuerpo)

    def test_por_defecto_impide_que_cargue_cookiebot(self):
        """Si se le deja cargar salen dos banners."""
        self.assertIn('cookiebot', self._cuerpo().lower())

    def test_se_puede_dejar_pasar_cookiebot_para_comparar(self):
        cuerpo = self._cuerpo(cookiebot='1')
        self.assertNotIn('createElement = function', cuerpo)

    def test_no_se_monta_dos_veces_en_una_página_de_django(self):
        """Las plantillas de Django ya traen el banner entero."""
        self.assertIn('if (w.__CONSENTIMIENTO__) return;', self._cuerpo())
