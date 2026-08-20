"""Tests A/B activos del funnel — para listarlos en el panel /funnels/.

El registro que MANDA vive en el front (`frontend/src/lib/formVariant.js`): es
el navegador quien asigna la variante y la persiste en localStorage. Esto es un
espejo en Python, solo para poder pintarlos en el panel sin ejecutar JS.

Para que no se separen, `tests/funnels/test_ab_panel.py` lee el fichero JS,
extrae sus experimentos y falla si no coinciden con esta lista.
"""

# Dónde acaba guardada la variante de cada familia de tests.
LEAD = 'Lead'
PRELLAMADA = 'Prellamada'

# (funnel, dónde se guarda, qué prueba, opción A, opción B)
# Cada opción es (etiqueta, código).
TESTS_AB = [
    # ── Landing: la variante viaja en el Lead (LeadRegister.utm_form_variant)
    ('cb-latam', LEAD, 'Fondo de la landing', ('papel', '57'), ('blanco', '58')),
    ('cb-us', LEAD, 'Fondo de la landing', ('papel', '59'), ('blanco', '60')),
    ('fi-latam', LEAD, 'Fondo de la landing', ('papel', '61'), ('blanco', '62')),
    ('cl-latam', LEAD, 'Fondo de la landing', ('papel', '63'), ('blanco', '64')),
    ('cl-eu', LEAD, 'Fondo de la landing', ('papel', '65'), ('blanco', '66')),
    ('cl-us', LEAD, 'Fondo de la landing', ('papel', '67'), ('blanco', '68')),
    ('cb-eu', LEAD, 'Captura de teléfono', ('sin checkbox', '51'), ('checkbox de WhatsApp', '52')),
    ('cb-eu-2', LEAD, 'Captura de teléfono', ('sin checkbox', '53'), ('checkbox de WhatsApp', '54')),
    ('fi-eu', LEAD, 'Captura de teléfono', ('checkbox de WhatsApp', '55'), ('campo obligatorio', '56')),

    # ── Página de vídeo: la variante viaja en la Prellamada
    #    (Prellamada.utm_form_variant → PreSchedule.utm_form_variant del CRM)
    ('cb-eu', PRELLAMADA, 'Footer del vídeo', ('con footer', '1'), ('sin footer', '2')),
    ('cb-latam', PRELLAMADA, 'Footer del vídeo', ('con footer', '3'), ('sin footer', '4')),
    ('cb-us', PRELLAMADA, 'Footer del vídeo', ('con footer', '5'), ('sin footer', '6')),
    ('fi-eu', PRELLAMADA, 'Footer del vídeo', ('con footer', '7'), ('sin footer', '8')),
    ('fi-latam', PRELLAMADA, 'Footer del vídeo', ('con footer', '9'), ('sin footer', '10')),
    ('cl-latam', PRELLAMADA, 'Footer del vídeo', ('con footer', '11'), ('sin footer', '12')),
    ('cl-eu', PRELLAMADA, 'Footer del vídeo', ('con footer', '13'), ('sin footer', '14')),
    ('cl-us', PRELLAMADA, 'Footer del vídeo', ('con footer', '15'), ('sin footer', '16')),
]


def tests_para_panel():
    """Los tests en el formato que consume la plantilla del panel."""
    return [
        {
            'funnel': funnel,
            'entidad': entidad,
            'prueba': prueba,
            'a_etiqueta': a[0], 'a_codigo': a[1],
            'b_etiqueta': b[0], 'b_codigo': b[1],
        }
        for funnel, entidad, prueba, a, b in TESTS_AB
    ]
