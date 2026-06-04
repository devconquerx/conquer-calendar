from django.db import migrations


PLANTILLAS = [
    {
        'nombre': 'Confirmación — Host',
        'color_encabezado': '#111827',
        'texto_encabezado': 'Nueva reserva confirmada',
        'cuerpo': 'Hola {{nombre_host}},\n\nTienes una nueva reserva confirmada con {{nombre_invitado}}.',
        'pie_pagina': 'Conquer Calendario · Este es un mensaje automático, no respondas a este correo.',
        'recordatorio_1_activo': False,
        'recordatorio_1_horas': 24,
        'recordatorio_2_activo': False,
        'recordatorio_2_horas': 1,
        'activa': True,
        'campos_visibles': [
            '{{nombre_evento}}',
            '{{nombre_invitado}}', '{{email_invitado}}', '{{telefono_invitado}}',
            '{{fecha_hora_host}}', '{{timezone_host}}', '{{fecha_hora_utc}}',
            '{{duracion}}',
            '{{google_event_url}}', '{{google_meet_url}}',
            '{{link_reserva}}', '{{link_cancelar}}',
        ],
    },
    {
        'nombre': 'Confirmación — Invitado',
        'color_encabezado': '#111827',
        'texto_encabezado': 'Tu reserva está confirmada',
        'cuerpo': 'Hola {{nombre_invitado}},\n\nTu reserva ha sido confirmada correctamente.',
        'pie_pagina': 'Conquer Calendario · Este es un mensaje automático, no respondas a este correo.',
        'recordatorio_1_activo': False,
        'recordatorio_1_horas': 24,
        'recordatorio_2_activo': False,
        'recordatorio_2_horas': 1,
        'activa': True,
        'campos_visibles': [
            '{{nombre_evento}}',
            '{{nombre_host}}', '{{email_host}}',
            '{{fecha_hora_invitado}}', '{{timezone}}', '{{fecha_hora_utc}}',
            '{{duracion}}',
            '{{google_event_url}}', '{{google_meet_url}}',
            '{{link_cancelar}}',
        ],
    },
    {
        'nombre': 'Recordatorio de reserva',
        'color_encabezado': '#111827',
        'texto_encabezado': 'Recordatorio: tienes una reunión próximamente',
        'cuerpo': 'Hola {{nombre_invitado}},\n\nTe recordamos que tienes una reunión programada próximamente.',
        'pie_pagina': 'Conquer Calendario · Este es un mensaje automático, no respondas a este correo.',
        'recordatorio_1_activo': True,
        'recordatorio_1_horas': 24,
        'recordatorio_2_activo': True,
        'recordatorio_2_horas': 1,
        'activa': True,
        'campos_visibles': [
            '{{nombre_evento}}',
            '{{nombre_host}}', '{{email_host}}',
            '{{fecha_hora_invitado}}', '{{timezone}}', '{{fecha_hora_utc}}',
            '{{duracion}}',
            '{{google_event_url}}', '{{google_meet_url}}',
            '{{link_cancelar}}',
        ],
    },
]


def actualizar_plantillas(apps, schema_editor):
    PlantillaCorreo = apps.get_model('bookings', 'PlantillaCorreo')
    for data in PLANTILLAS:
        nombre = data.pop('nombre')
        PlantillaCorreo.objects.filter(nombre=nombre).update(**data)
        data['nombre'] = nombre  # restaurar para idempotencia


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0016_configcorreodefault'),
    ]

    operations = [
        migrations.RunPython(actualizar_plantillas, migrations.RunPython.noop),
    ]
