# -*- coding: utf-8 -*-
"""Iguala el landing de Conquer Blocks EU-2 al de EU (blocks-eu-2 no debe tener copy propia).

Verificado contra conquerx-funnels-new: `cb-eu-2` es un clon de `cb-eu` bajo
una URL/vídeo nuevos (mismo formulario, mismo StepForm/scoring, mismo
Calendly) — la ÚNICA diferencia real es un VSL más corto y un experimento A/B
de WhatsApp opt-in independiente (`form_variant_cb_eu_2`, ya replicado en
`frontend/src/components/landing/LandingForm.jsx`). El commit fundacional del
viejo lo dice textual: "Habilitar mismo flujo de teléfono y utm_title que
cb-eu para el nuevo cb-eu-2".

`seed_data/blocks_eu_2.json` (0021) se sembró con un `landing` propio
(título/bullets/instructor/disclaimer distintos) — un error de esta sesión,
no algo que existiera en el viejo. Este parche iguala `config.landing` de
FullEu2 al de FullEu, y limpia el `calendly_url` que quedó en sus
`score_ranges` (FullEu no lo tiene: Blocks resuelve el booking por
EventType/host interno, no por Calendly directo — ver 0023).

`config.video` NO se toca: esa sí es la diferencia real (VSL corto).

Blocks EU-2 ya está desplegado con `get_or_create` (0021), así que corregir
el JSON de `seed_data/` no llega a la fila existente — hay que parchearla
aquí, igual que 0003/0012/0019/0020.
"""
from django.db import migrations


def _patch(apps, use_eu_2_calendly):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    eu = FunnelForm.objects.filter(key='FullEu').first()
    eu2 = FunnelForm.objects.filter(key='FullEu2').first()
    if not eu or not eu2:
        return

    cfg2 = eu2.config or {}

    if use_eu_2_calendly:
        # backwards: restaura la copia y los calendly_url originales de eu-2.
        cfg2['landing'] = _OLD_EU_2_LANDING
        for rango, url in zip(cfg2.get('score_ranges', []), _OLD_CALENDLY_URLS):
            rango['calendly_url'] = url
    else:
        # forwards: copia el landing de FullEu tal cual, y quita calendly_url.
        cfg_eu = eu.config or {}
        cfg2['landing'] = cfg_eu.get('landing', cfg2.get('landing'))
        for rango in cfg2.get('score_ranges', []):
            rango.pop('calendly_url', None)

    eu2.config = cfg2
    eu2.save(update_fields=['config'])


_OLD_EU_2_LANDING = {
    'title': 'Consigue un <strong>empleo remoto</strong> de 36,000€ a 98,000€ <strong>anuales</strong>, convirtiéndote en Desarrollador de Software <strong>en menos de 12 meses</strong>',
    'bullets': [
        'Descubre la metodología que te permite aprender a <strong>programar desde cero con éxito</strong>, haciéndolo con la misma facilidad con la que escribes en español.',
        'Conviértete en un perfil de élite y consigue trabajo en tiempo récord gracias a un sistema que te enseña a ser 4 veces más productivo usando <strong>Inteligencia Artificial</strong>.',
        'Accede al único método del mercado que <strong>te garantiza un empleo en menos de 10 entrevistas </strong>o te devolvemos el 100% de tu dinero.',
    ],
    'subtitle': 'Presentación exclusiva de 10 minutos',
    'buttonText': 'VER VÍDEO GRATIS',
    'disclaimer': 'El curso y la clase son únicamente educativos e informativos. No constituyen asesoramiento financiero ni laboral. Los resultados no están garantizados y pueden variar según cada persona. Puedes contactarnos enviándonos un email a contacto@conquerblocks.com',
    'instructor': {
        'name': 'Bienvenido Sáez',
        'imageUrl': 'https://cdn.prod.website-files.com/6993dad0d51e8b544baf5340/69c31472ca0de4df3af0d1fc_bienvenido-saez-2.avif',
        'description': 'Con casi 20 años de experiencia, Bienvenido es el arquitecto del método formativo que ha llevado a Conquer Blocks a ser reconocida por la revista Forbes.<br><br>A través de la presentación exclusiva que estás a punto de ver, te mostrará cómo ha logrado que más de 6.000 personas, partiendo desde cero, dominen la tecnología y accedan a los salarios de la élite del mercado.',
    },
    'description': '... sin importar tu experiencia previa, edad ni profesión actual.',
}

_OLD_CALENDLY_URLS = [
    'https://calendly.com/d/cm8m-fpp-7sc/sesion-de-consultoria-conquer-blocks-eu',
    'https://calendly.com/d/cqv6-8dc-tyr/sesion-de-consultoria-conquer-blocks-eu',
]


def forwards(apps, schema_editor):
    _patch(apps, use_eu_2_calendly=False)


def backwards(apps, schema_editor):
    _patch(apps, use_eu_2_calendly=True)


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0023_blocks_evento_prueba'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
