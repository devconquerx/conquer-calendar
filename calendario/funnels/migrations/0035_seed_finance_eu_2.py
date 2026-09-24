# -*- coding: utf-8 -*-
"""Crea la segunda landing EU de Conquer Finance (finance-eu-2, fi-eu-2).

LP2 pedida por marketing (24-sep-2026) con las campañas de CF paradas: mismo
diseño que la landing de finance-eu y copy nueva, más prudente (educativa, sin
cifras de resultados). Mismo esquema que blocks-eu-2: FunnelForm propio con su
landing y su vídeo, que comparte escuela+región con finance-eu.

Se clona la fila de finance-eu TAL COMO ESTÉ en cada BD en vez de sembrar un
JSON: así hereda el quiz, el scoring, los textos del StepForm, el vídeo y
—sobre todo— los `score_ranges` con los EventTypes de ESE entorno, cuyos ids
difieren entre local y producción. Solo se sustituye la copy de la landing.
El vídeo es de momento el mismo VSL de finance-eu; cuando llegue el de la LP2
se cambia en `config.video` desde el admin.

Teléfono siempre visible y obligatorio (`phoneRequired`, como la variante 56
de finance-eu, que es la que muestra el diseño). La LP2 no corre ningún A/B.

Idempotente: `get_or_create` por `key` → no pisa ediciones hechas después en
el admin.
"""
import copy

from django.db import migrations

_LANDING_EU_2 = {
    'subtitle': '· VÍDEO <strong>GRATIS</strong> DE 15 MINUTOS ·',
    'title': (
        'Descubre una forma estructurada de <strong>comprender el trading y '
        'sus riesgos</strong>, empezando por los conceptos esenciales.'
    ),
    'description': (
        'Una introducción para quienes quieren empezar a aprender. Completa el '
        'formulario y haz clic en «VER VÍDEO GRATIS» para acceder.'
    ),
    'bullets': [
        'Conoce los fundamentos del trading y cómo funciona la operativa en los mercados financieros.',
        'Entiende las cuentas fondeadas: evaluaciones, costes, condiciones y riesgos que debes conocer.',
        'Explora conceptos de diversificación y planificación a largo plazo para ampliar tu educación financiera.',
    ],
    'consentText': 'Usaremos tus datos para facilitarte el acceso al vídeo y gestionar tu solicitud.',
    'consentPrivacyPre': 'Consulta cómo tratamos tus datos en nuestra',
    'consentPrivacyLink': 'política de privacidad.',
    'buttonText': 'VER VÍDEO GRATIS',
    'instructor': {
        'name': 'Félix Fuertes',
        'role': '',
        'imageUrl': 'https://cdn.prod.website-files.com/66fa7f848e37dcc492c20064/66fa7f848e37dcc492c2012f_felix_1.avif',
        'description': (
            'Félix es CEO de Conquer Finance y formador en trading y mercados '
            'financieros. En este vídeo presenta los fundamentos de su enfoque '
            'educativo y los aspectos que conviene conocer antes de empezar a operar.'
        ),
    },
    'disclaimer': [
        'Contenido educativo general. No constituye asesoramiento financiero personalizado.',
        'La formación no garantiza ingresos, rentabilidad ni la obtención de una cuenta fondeada. '
        'Operar en mercados financieros implica riesgos y puede ocasionar pérdidas.',
        'El acceso a cuentas fondeadas depende de evaluaciones, costes y condiciones de terceros. '
        'Contacto: contacto@conquerfinance.com',
    ],
    # La copy ya trae su propia línea de contacto: sin esto Landing.jsx añade
    # "Puedes contactarnos enviándonos un email a …" detrás del último párrafo.
    'disclaimerContact': False,
    'phoneRequired': True,
}


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    if FunnelForm.objects.filter(key='PropTradingEu2').exists():
        return
    eu = FunnelForm.objects.filter(slug='finance-eu').first()
    if eu is None:
        return
    config = copy.deepcopy(eu.config or {})
    config['key'] = 'PropTradingEu2'
    landing = dict(config.get('landing') or {})
    # Del landing de finance-eu solo sobrevive lo que no es copy (p.ej. el
    # checkbox de WhatsApp si lo tuviera fijo); los textos son todos nuevos.
    for clave in ('whatsappOptin', 'showPhone', 'commercialConsent'):
        landing.pop(clave, None)
    landing.update(_LANDING_EU_2)
    config['landing'] = landing
    FunnelForm.objects.create(
        key='PropTradingEu2',
        slug='finance-eu-2',
        escuela=eu.escuela,
        region=eu.region,
        nombre='Conquer Finance — EU 2 (LP2)',
        config=config,
        activo=True,
    )


def backwards(apps, schema_editor):
    # No-op: no borramos datos sembrados al revertir (igual que 0006/0021).
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0034_contenido_bitacora_coding_week'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
