import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('event_types', '0013_incremento_segun_duracion'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EnlaceUnico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('usado', models.BooleanField(default=False)),
                ('usado_en', models.DateTimeField(blank=True, null=True)),
                ('event_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enlaces_unicos',
                    to='event_types.eventtype',
                )),
                ('creado_por', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enlaces_unicos_creados',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'enlace único',
                'verbose_name_plural': 'enlaces únicos',
                'db_table': 'event_type_enlaces_unicos',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.AddIndex(
            model_name='enlaceunico',
            index=models.Index(fields=['token'], name='ix_enlace_unico_token'),
        ),
    ]
