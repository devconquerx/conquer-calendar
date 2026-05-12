from django.db import migrations, models
from django.utils.text import slugify


def backfill_slugs_event_types(apps, schema_editor):
    EventType = apps.get_model('event_types', 'EventType')
    por_host = {}
    for et in EventType.objects.order_by('host_id', 'pk'):
        base = slugify(et.nombre) or 'evento'
        usados_host = por_host.setdefault(et.host_id, set())
        candidato = base
        i = 2
        while candidato in usados_host:
            candidato = f'{base}-{i}'
            i += 1
        et.slug = candidato
        et.save(update_fields=['slug'])
        usados_host.add(candidato)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventtype',
            name='slug',
            field=models.SlugField(max_length=120, null=True, blank=True),
        ),
        migrations.RunPython(backfill_slugs_event_types, reverse_noop),
        migrations.AlterField(
            model_name='eventtype',
            name='slug',
            field=models.SlugField(max_length=120),
        ),
        migrations.AddConstraint(
            model_name='eventtype',
            constraint=models.UniqueConstraint(fields=['host', 'slug'], name='uq_event_type_host_slug'),
        ),
        migrations.AddIndex(
            model_name='eventtype',
            index=models.Index(fields=['host', 'activo'], name='ix_event_type_host_activo'),
        ),
    ]
