from django.db import migrations, models
from django.utils.text import slugify


def backfill_slugs_users(apps, schema_editor):
    User = apps.get_model('users', 'User')
    usados = set()
    for u in User.objects.order_by('pk'):
        base = slugify(u.username) or 'usuario'
        candidato = base
        i = 2
        while candidato in usados:
            candidato = f'{base}-{i}'
            i += 1
        u.slug = candidato
        u.save(update_fields=['slug'])
        usados.add(candidato)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_alter_user_options_remove_user_full_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='slug',
            field=models.SlugField(max_length=80, null=True, blank=True, db_index=False),
        ),
        migrations.RunPython(backfill_slugs_users, reverse_noop),
        migrations.AlterField(
            model_name='user',
            name='slug',
            field=models.SlugField(max_length=80, unique=True),
        ),
    ]
