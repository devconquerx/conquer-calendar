from django.db import migrations


# Los tres dominios de las academias están dados de alta en la región UE de
# Mailgun; el de la app sigue en la de EEUU. Si se cambia la región de un
# dominio en Mailgun hay que cambiarla también aquí (o desde el admin), o los
# envíos fallan con «Unknown sender domain».
DOMINIOS = [
    {
        'dominio': 'conquerblocks.com',
        'nombre': 'Conquer Blocks',
        'region': 'eu',
        'from_email': 'Conquer Blocks <noreply@conquerblocks.com>',
        'reply_to': 'contacto@conquerblocks.com',
    },
    {
        'dominio': 'conquerfinance.com',
        'nombre': 'Conquer Finance',
        'region': 'eu',
        'from_email': 'Conquer Finance <noreply@conquerfinance.com>',
        'reply_to': 'contacto@conquerfinance.com',
    },
    {
        'dominio': 'conquerlanguages.com',
        'nombre': 'Conquer Languages',
        'region': 'eu',
        'from_email': 'Conquer Languages <noreply@conquerlanguages.com>',
        'reply_to': 'contacto@conquerlanguages.com',
    },
    {
        'dominio': 'calendar.conquerx.com',
        'nombre': 'Conquer Calendario',
        'region': 'us',
        'from_email': 'Conquer Calendario <noreply@calendar.conquerx.com>',
        'reply_to': '',
    },
]


def crear_dominios(apps, schema_editor):
    DominioRemitente = apps.get_model('bookings', 'DominioRemitente')
    for datos in DOMINIOS:
        DominioRemitente.objects.get_or_create(
            dominio=datos['dominio'],
            defaults={k: v for k, v in datos.items() if k != 'dominio'},
        )


def borrar_dominios(apps, schema_editor):
    DominioRemitente = apps.get_model('bookings', 'DominioRemitente')
    # Solo los que crea esta migración y que nadie esté usando: si alguien ya
    # los asignó a una plantilla, revertir no debe llevárselos por delante.
    DominioRemitente.objects.filter(
        dominio__in=[d['dominio'] for d in DOMINIOS],
        plantillas__isnull=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0027_dominioremitente_plantillacorreo_formato_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_dominios, borrar_dominios),
    ]
