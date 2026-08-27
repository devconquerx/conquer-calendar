"""
Migración de datos: de bloques colgados del host a horarios con nombre.

Dos movimientos, ninguno cambia el comportamiento de nadie:

1. Cada usuario estrena su horario "Default" y se le cuelgan los bloques que ya
   tenía. Quien no use la función no debería notar el cambio.
2. Cada EventTypeXHost que tuviera disponibilidad propia (las tablas
   `disponibilidad_etxh` y `disponibilidad_fecha_etxh`, que desaparecen en la
   migración siguiente) estrena un horario con el nombre de su evento, y el
   etxh pasa a apuntarlo.
"""
from django.db import migrations


NOMBRE_DEFAULT = 'Default'


def _nombre_libre(Horario, host_id, base):
    """Respeta el unique(host, nombre) añadiendo un sufijo si hace falta."""
    base = (base or 'Horario')[:70]
    nombre = base
    n = 2
    while Horario.objects.filter(host_id=host_id, nombre=nombre).exists():
        nombre = f'{base} ({n})'
        n += 1
    return nombre


def migrar(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Horario = apps.get_model('availability', 'Horario')
    BloqueHorarioSemanal = apps.get_model('availability', 'BloqueHorarioSemanal')
    BloqueHorarioFecha = apps.get_model('availability', 'BloqueHorarioFecha')
    EventTypeXHost = apps.get_model('event_types', 'EventTypeXHost')
    DisponibilidadEtxh = apps.get_model('event_types', 'DisponibilidadEtxh')
    DisponibilidadFechaEtxh = apps.get_model('event_types', 'DisponibilidadFechaEtxh')

    # --- 1. El horario Default de cada persona ---------------------------------
    # Se crea para todos, también para quien no tenga ni un bloque: la UI y el
    # motor de slots dan por hecho que siempre hay un default al que caer.
    defaults = {}
    for user in User.objects.all().iterator():
        horario, _ = Horario.objects.get_or_create(
            host_id=user.pk,
            nombre=NOMBRE_DEFAULT,
            defaults={'es_default': True},
        )
        if not horario.es_default:
            horario.es_default = True
            horario.save(update_fields=['es_default'])
        defaults[user.pk] = horario

    for modelo in (BloqueHorarioSemanal, BloqueHorarioFecha):
        for bloque in modelo.objects.filter(horario__isnull=True).iterator():
            horario = defaults.get(bloque.host_id)
            if horario is None:
                # Bloque huérfano de un usuario que ya no está: se descarta con
                # el mismo efecto que tenía (ninguno, nadie lo consultaba).
                continue
            bloque.horario = horario
            bloque.save(update_fields=['horario'])

    # --- 2. La disponibilidad por evento pasa a horario propio -----------------
    etxh_con_disponibilidad = set(
        DisponibilidadEtxh.objects.values_list('etxh_id', flat=True)
    ) | set(
        DisponibilidadFechaEtxh.objects.values_list('etxh_id', flat=True)
    )

    for etxh in EventTypeXHost.objects.filter(pk__in=etxh_con_disponibilidad).iterator():
        nombre = _nombre_libre(Horario, etxh.host_id, etxh.event_type.nombre)
        horario = Horario.objects.create(
            host_id=etxh.host_id, nombre=nombre, es_default=False,
        )

        BloqueHorarioSemanal.objects.bulk_create([
            BloqueHorarioSemanal(
                host_id=etxh.host_id,
                horario=horario,
                dia_semana=d.dia_semana,
                hora_inicio=d.hora_inicio,
                hora_fin=d.hora_fin,
            )
            for d in DisponibilidadEtxh.objects.filter(etxh_id=etxh.pk)
        ], ignore_conflicts=True)

        BloqueHorarioFecha.objects.bulk_create([
            BloqueHorarioFecha(
                host_id=etxh.host_id,
                horario=horario,
                fecha=f.fecha,
                hora_inicio=f.hora_inicio,
                hora_fin=f.hora_fin,
            )
            for f in DisponibilidadFechaEtxh.objects.filter(etxh_id=etxh.pk)
        ], ignore_conflicts=True)

        etxh.horario = horario
        etxh.save(update_fields=['horario'])


def revertir(apps, schema_editor):
    """
    Deshace lo que se pueda: suelta los bloques de su horario y borra los
    horarios. Las tablas viejas siguen intactas —esta migración solo lee de
    ellas—, así que el estado anterior se recupera entero.
    """
    Horario = apps.get_model('availability', 'Horario')
    EventTypeXHost = apps.get_model('event_types', 'EventTypeXHost')
    BloqueHorarioSemanal = apps.get_model('availability', 'BloqueHorarioSemanal')
    BloqueHorarioFecha = apps.get_model('availability', 'BloqueHorarioFecha')

    EventTypeXHost.objects.update(horario=None)
    # Primero los horarios de evento: sus bloques son copias creadas aquí y se
    # van con ellos por CASCADE. Las filas originales siguen intactas en
    # disponibilidad_etxh, que esta migración solo lee.
    Horario.objects.filter(es_default=False).delete()
    # Los del Default sí son los bloques de siempre: se sueltan, no se borran.
    BloqueHorarioSemanal.objects.update(horario=None)
    BloqueHorarioFecha.objects.update(horario=None)
    Horario.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0034_eventtypexhost_horario'),
        ('availability', '0006_alter_bloquehorariofecha_options_and_more'),
        ('users', '0004_user_country'),
    ]

    operations = [
        migrations.RunPython(migrar, revertir),
    ]
