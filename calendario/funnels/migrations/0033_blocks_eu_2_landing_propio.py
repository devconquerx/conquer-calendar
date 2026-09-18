# -*- coding: utf-8 -*-
"""Devuelve a blocks-eu-2 su copy propia de landing (revierte 0024).

0024 igualó el `landing` de `FullEu2` al de `FullEu` dando por hecho que la
copy propia sembrada en 0021 era un error de sesión. No lo era: 0021 la
capturó en vivo de www.conquerblocks.com/conquer-blocks/clase-2-online-gratuita-eu
y marketing confirma (18-sep-2026, con el Webflow de esa página delante) que
ese era el copy real de la segunda landing —titular de 36.000€-98.000€, tag
"Presentación exclusiva de 10 minutos" acorde al VSL corto, bullets de
metodología/IA/garantía y la bio larga de Bienvenido—. Desde la migración
las dos landings EU mostraban el mismo texto.

Se restauran SOLO las claves de copy (`title`, `bullets`, `subtitle`,
`buttonText`, `disclaimer`, `instructor`, `description`). El resto del dict
—hoy `whatsappOptin` (0027), y `commercialConsent` si 0026 lo hubiera
puesto— se conserva tal cual: son ajustes posteriores e independientes del
texto. `instructor` va entero, así que se queda sin `role` (la copy vieja no
lo traía); la foto no cambia en pantalla porque Landing.jsx prefiere
`assets.instructorPhoto` del tema antes que `instructor.imageUrl`.

NO se toca lo otro que hizo 0024: quitar el `calendly_url` de los
`score_ranges` de FullEu2 sí era correcto (Blocks resuelve el booking por
EventType/host interno, ver 0023). `config.video` tampoco: el VSL corto es la
otra diferencia real entre ambas landings.

Se parchea la fila porque `landing` sólo vive en la BD; el JSON de
`seed_data/` (actualizado en paralelo) solo entra en BDs frescas.
"""
from django.db import migrations

COPY_KEYS = ('title', 'bullets', 'subtitle', 'buttonText', 'disclaimer',
             'instructor', 'description')

_LANDING_EU_2 = {
    'title': (
        'Consigue un <strong>empleo remoto</strong> de 36,000€ a 98,000€ '
        '<strong>anuales</strong>, convirtiéndote en Desarrollador de Software '
        '<strong>en menos de 12 meses</strong>'
    ),
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


def _aplica_copy(apps, copy):
    """Escribe `copy` sobre las claves de texto del landing de FullEu2."""
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    eu2 = FunnelForm.objects.filter(key='FullEu2').first()
    if not eu2 or not copy:
        return
    config = dict(eu2.config or {})
    landing = dict(config.get('landing') or {})
    for clave in COPY_KEYS:
        if clave in copy:
            landing[clave] = copy[clave]
    config['landing'] = landing
    eu2.config = config
    eu2.save(update_fields=['config'])


def forwards(apps, schema_editor):
    _aplica_copy(apps, _LANDING_EU_2)


def backwards(apps, schema_editor):
    # Vuelve a dejar la copy de FullEu, que es lo que dejó 0024.
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    eu = FunnelForm.objects.filter(key='FullEu').first()
    _aplica_copy(apps, (eu.config or {}).get('landing') if eu else None)


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0032_ai_eu_telefono_obligatorio'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
