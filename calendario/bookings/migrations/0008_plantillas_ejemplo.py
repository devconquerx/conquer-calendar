from django.db import migrations


PLANTILLAS = [
    {
        'nombre': 'Confirmación — Host',
        'texto_encabezado': 'Nueva reserva confirmada',
        'cuerpo': (
            'Hola {{nombre_host}},\n\n'
            'Tienes una nueva reserva confirmada.\n\n'
            'Evento: {{nombre_evento}}\n'
            'Invitado: {{nombre_invitado}} ({{email_invitado}})\n'
            'Fecha y hora: {{fecha_hora}}\n'
            'Duración: {{duracion}} minutos\n'
            '{{google_meet_url}}\n\n'
            'El invitado puede cancelar desde el siguiente enlace:\n'
            '{{link_cancelar}}'
        ),
        'pie_pagina': 'Conquer Calendario · Este es un mensaje automático, no respondas a este correo.',
        'recordatorio_1_activo': False,
        'recordatorio_1_horas': 24,
        'recordatorio_2_activo': False,
        'recordatorio_2_horas': 1,
    },
    {
        'nombre': 'Confirmación — Invitado',
        'texto_encabezado': 'Tu reserva está confirmada',
        'cuerpo': (
            'Hola {{nombre_invitado}},\n\n'
            'Tu reserva ha sido confirmada correctamente.\n\n'
            'Evento: {{nombre_evento}}\n'
            'Con: {{nombre_host}}\n'
            'Fecha y hora: {{fecha_hora}}\n'
            'Duración: {{duracion}} minutos\n'
            '{{google_meet_url}}\n\n'
            '¿Necesitas cancelar? Puedes hacerlo aquí:\n'
            '{{link_cancelar}}'
        ),
        'pie_pagina': 'Conquer Calendario · Este es un mensaje automático, no respondas a este correo.',
        'recordatorio_1_activo': False,
        'recordatorio_1_horas': 24,
        'recordatorio_2_activo': False,
        'recordatorio_2_horas': 1,
    },
    {
        'nombre': 'Recordatorio de reserva',
        'texto_encabezado': 'Recordatorio: tienes una reunión próximamente',
        'cuerpo': (
            'Hola {{nombre_invitado}},\n\n'
            'Te recordamos que tienes una reunión programada.\n\n'
            'Evento: {{nombre_evento}}\n'
            'Con: {{nombre_host}}\n'
            'Fecha y hora: {{fecha_hora}}\n'
            'Duración: {{duracion}} minutos\n'
            '{{google_meet_url}}\n\n'
            'Si necesitas cancelar:\n'
            '{{link_cancelar}}'
        ),
        'pie_pagina': 'Conquer Calendario · Este es un mensaje automático, no respondas a este correo.',
        'recordatorio_1_activo': True,
        'recordatorio_1_horas': 24,
        'recordatorio_2_activo': True,
        'recordatorio_2_horas': 1,
    },
]


def crear_plantillas(apps, schema_editor):
    PlantillaCorreo = apps.get_model('bookings', 'PlantillaCorreo')
    for data in PLANTILLAS:
        PlantillaCorreo.objects.get_or_create(nombre=data['nombre'], defaults=data)


def borrar_plantillas(apps, schema_editor):
    PlantillaCorreo = apps.get_model('bookings', 'PlantillaCorreo')
    PlantillaCorreo.objects.filter(nombre__in=[p['nombre'] for p in PLANTILLAS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0007_reserva_recordatorios_enviados'),
    ]

    operations = [
        migrations.RunPython(crear_plantillas, borrar_plantillas),
    ]
