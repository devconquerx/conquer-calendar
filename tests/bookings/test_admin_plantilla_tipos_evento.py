"""
Asignar una plantilla a varios tipos de evento desde la propia plantilla.

Antes había que entrar tipo de evento por tipo de evento para engancharle la
plantilla. Ahora el formulario de la plantilla trae los tres huecos de
ConfigCorreoEvento (host, invitado, recordatorio) y sincroniza las configs al
guardar. Lo que hay que proteger es que quitar un tipo de evento de la caja
NO cambie los otros dos correos ni la plantilla de nadie más: solo vacía ese
hueco, que es lo que devuelve el evento a la configuración global.
"""
from django.test import TestCase

from calendario.bookings.admin import PlantillaCorreoAdminForm
from calendario.bookings.models import ConfigCorreoEvento, PlantillaCorreo
from tests.factories import crear_event_type, crear_host


def crear_plantilla(nombre='Plantilla test'):
    return PlantillaCorreo.objects.create(
        nombre=nombre,
        texto_encabezado='Hola',
        cuerpo='Cuerpo de prueba',
    )


def datos_form(plantilla, **extra):
    """Los campos obligatorios del form, para no repetirlos en cada test."""
    datos = {
        'nombre': plantilla.nombre,
        'texto_encabezado': plantilla.texto_encabezado,
        'cuerpo': plantilla.cuerpo,
        'color_encabezado': plantilla.color_encabezado,
        'formato': plantilla.formato,
        'pie_pagina': '',
        'recordatorio_1_horas': plantilla.recordatorio_1_horas,
        'recordatorio_2_horas': plantilla.recordatorio_2_horas,
        'activa': 'on',
    }
    datos.update(extra)
    return datos


class AsignarPlantillaATiposEventoTest(TestCase):

    def setUp(self):
        self.host = crear_host()
        self.plantilla = crear_plantilla()
        self.et1 = crear_event_type(self.host, nombre='Demo 30')
        self.et2 = crear_event_type(self.host, nombre='Onboarding')

    def guardar(self, **campos):
        form = PlantillaCorreoAdminForm(
            data=datos_form(self.plantilla, **campos),
            instance=self.plantilla,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

    def test_asigna_a_varios_tipos_de_una_vez(self):
        self.guardar(tipos_correo_invitado=[self.et1.pk, self.et2.pk])

        for et in (self.et1, self.et2):
            config = ConfigCorreoEvento.objects.get(event_type=et)
            self.assertEqual(config.plantilla_confirmacion_inv, self.plantilla)
            self.assertIsNone(config.plantilla_confirmacion_host)

    def test_cada_hueco_va_por_su_cuenta(self):
        self.guardar(
            tipos_correo_host=[self.et1.pk],
            tipos_correo_invitado=[self.et1.pk, self.et2.pk],
            tipos_recordatorio=[self.et2.pk],
        )

        config1 = ConfigCorreoEvento.objects.get(event_type=self.et1)
        self.assertEqual(config1.plantilla_confirmacion_host, self.plantilla)
        self.assertEqual(config1.plantilla_confirmacion_inv, self.plantilla)
        self.assertIsNone(config1.plantilla_recordatorio)

        config2 = ConfigCorreoEvento.objects.get(event_type=self.et2)
        self.assertIsNone(config2.plantilla_confirmacion_host)
        self.assertEqual(config2.plantilla_confirmacion_inv, self.plantilla)
        self.assertEqual(config2.plantilla_recordatorio, self.plantilla)

    def test_al_reabrir_el_form_vienen_marcados_los_que_ya_la_usan(self):
        self.guardar(tipos_correo_host=[self.et1.pk])

        form = PlantillaCorreoAdminForm(instance=self.plantilla)
        self.assertEqual(form.fields['tipos_correo_host'].initial, [self.et1.pk])
        self.assertEqual(form.fields['tipos_correo_invitado'].initial, [])

    def test_quitar_uno_lo_devuelve_a_la_config_global(self):
        self.guardar(tipos_correo_invitado=[self.et1.pk, self.et2.pk])
        self.guardar(tipos_correo_invitado=[self.et1.pk])

        self.assertEqual(
            ConfigCorreoEvento.objects.get(event_type=self.et1).plantilla_confirmacion_inv,
            self.plantilla,
        )
        # Sin plantilla propia y sin nada más configurado, la config sobra:
        # el evento vuelve a resolver por la global.
        self.assertFalse(ConfigCorreoEvento.objects.filter(event_type=self.et2).exists())

    def test_quitar_un_hueco_no_toca_los_otros(self):
        self.guardar(
            tipos_correo_host=[self.et1.pk],
            tipos_correo_invitado=[self.et1.pk],
        )
        self.guardar(tipos_correo_invitado=[self.et1.pk])

        config = ConfigCorreoEvento.objects.get(event_type=self.et1)
        self.assertIsNone(config.plantilla_confirmacion_host)
        self.assertEqual(config.plantilla_confirmacion_inv, self.plantilla)

    def test_no_pisa_la_plantilla_de_otra_plantilla(self):
        otra = crear_plantilla('Otra plantilla')
        ConfigCorreoEvento.objects.create(
            event_type=self.et2,
            plantilla_confirmacion_inv=otra,
        )

        self.guardar(tipos_correo_invitado=[self.et1.pk])

        self.assertEqual(
            ConfigCorreoEvento.objects.get(event_type=self.et2).plantilla_confirmacion_inv,
            otra,
        )

    def test_los_inactivos_no_se_ofrecen_pero_no_se_desasignan(self):
        self.guardar(tipos_correo_host=[self.et1.pk, self.et2.pk])
        self.et2.activo = False
        self.et2.save(update_fields=['activo'])

        form = PlantillaCorreoAdminForm(instance=self.plantilla)
        opciones = set(form.fields['tipos_correo_invitado'].queryset.values_list('pk', flat=True))
        self.assertNotIn(self.et2.pk, opciones)

        # En el hueco donde sí la usa sigue apareciendo, para que al guardar
        # sin tocar nada no se pierda la asignación.
        opciones_host = set(form.fields['tipos_correo_host'].queryset.values_list('pk', flat=True))
        self.assertIn(self.et2.pk, opciones_host)

        self.guardar(tipos_correo_host=[self.et1.pk, self.et2.pk])
        self.assertEqual(
            ConfigCorreoEvento.objects.get(event_type=self.et2).plantilla_confirmacion_host,
            self.plantilla,
        )

    def test_una_plantilla_nueva_tambien_puede_asignarse(self):
        form = PlantillaCorreoAdminForm(data=datos_form(
            PlantillaCorreo(nombre='Nueva', texto_encabezado='Hola', cuerpo='Cuerpo'),
            tipos_recordatorio=[self.et1.pk],
        ))
        self.assertTrue(form.is_valid(), form.errors)
        plantilla = form.save()

        self.assertEqual(
            ConfigCorreoEvento.objects.get(event_type=self.et1).plantilla_recordatorio,
            plantilla,
        )
