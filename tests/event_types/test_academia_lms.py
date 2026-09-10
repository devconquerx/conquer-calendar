"""
La academia del LMS se elige por nombre, no tecleando su id.

El LMS es multi-academia y su mutación de sesiones pide un `academy_id` entero.
Ese número es suyo y no significa nada de este lado, así que quien configura un
tipo de evento elige «Conquer Languages» y el formulario guarda el 3. Es el mismo
patrón que ya usan las conversiones (`SCHOOL_PIXEL_META`, `SCHOOL_CUSTOMER_GOOGLE`):
la escuela se elige, el id opaco vive en el código.

Lo que cubren estos tests:

  * el catálogo es el de la base de producción del LMS, y no incluye Conquer
    Business, que existe allí pero todavía está en desarrollo;
  * el formulario rechaza un id que no sea de una academia real —antes cualquier
    número entraba y la sesión viajaba a una academia inexistente—;
  * sigue siendo opcional: dejarlo vacío guarda sin protestar;
  * y el panel pinta el desplegable con la academia guardada ya elegida. El
    template escribe este campo a mano en vez de usar `{{ form.campo }}`, así que
    las opciones del modelo no llegan solas a la pantalla.
"""
from django.test import Client, TestCase
from django.urls import reverse

from calendario.event_types.forms import EventTypeForm
from calendario.event_types.models import EventType
from tests.factories import crear_host


def _datos(**extra):
    """El mínimo que el formulario da por bueno, más lo que pida el test."""
    datos = dict(
        nombre='Clase 1 a 1 de inglés', duracion_minutos=45,
        incremento_inicio_minutos=15, aviso_minimo_minutos=0,
        aviso_maximo_dias=60, confirmacion_tipo='default', crm_destino='none',
        registrar_en_academia=True,
    )
    datos.update(extra)
    return datos


class CatalogoAcademiasTest(TestCase):

    def test_son_las_academias_del_lms(self):
        self.assertEqual(
            dict(EventType.AcademiaLms.choices),
            {1: 'Conquer Blocks', 2: 'Conquer Finance', 3: 'Conquer Languages'},
        )

    def test_business_no_se_ofrece_todavia(self):
        """Existe en el LMS con el id 4, pero está en desarrollo y no se usa.
        Ofrecerla mandaría sesiones a una academia que nadie mira."""
        self.assertNotIn(4, dict(EventType.AcademiaLms.choices))


class FormularioAcademiaTest(TestCase):

    def setUp(self):
        self.host = crear_host(email='academia.host@test.com')

    def test_guarda_el_id_de_la_academia_elegida(self):
        form = EventTypeForm(data=_datos(academia_lms_id=EventType.AcademiaLms.LANGUAGES))
        self.assertTrue(form.is_valid(), form.errors)
        et = form.save(commit=False)
        et.host = self.host
        et.save()
        self.assertEqual(et.academia_lms_id, 3)

    def test_un_id_que_no_es_de_ninguna_academia_no_pasa(self):
        """El campo era un número libre: un 7 mal tecleado se guardaba tan
        contento y la sesión llegaba al LMS con una academia que no existe."""
        form = EventTypeForm(data=_datos(academia_lms_id=7))
        self.assertFalse(form.is_valid())
        self.assertIn('academia_lms_id', form.errors)

    def test_sigue_siendo_opcional(self):
        """Sin academia la sesión se registra igual y cuenta para las métricas
        por profesor; solo queda fuera de los recuentos por academia."""
        form = EventTypeForm(data=_datos(academia_lms_id=''))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['academia_lms_id'])


class PanelAcademiaTest(TestCase):
    """El formulario del panel, que es donde esto se usa de verdad."""

    def setUp(self):
        self.host = crear_host(email='panel.academia@test.com')
        self.host.set_password('secreta')
        self.host.save()
        self.client = Client()
        self.client.force_login(self.host)
        self.et = EventType.objects.create(
            host=self.host, nombre='Clase de inglés', slug='clase-de-ingles',
            duracion_minutos=45, academia_lms_id=EventType.AcademiaLms.FINANCE,
        )

    def test_el_panel_pinta_el_desplegable_con_la_academia_guardada(self):
        url = reverse('panel_event_types:event_type_update', args=[self.et.pk])
        html = self.client.get(url).content.decode()

        self.assertIn('Conquer Languages', html)
        self.assertIn('<option value="2" selected>Conquer Finance</option>', html)
