from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Grupo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150)),
                ('descripcion', models.TextField(blank=True, default='')),
                ('permite_ver_reservas_grupo', models.BooleanField(default=False, verbose_name='Pueden ver reservas del grupo')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'grupo',
                'verbose_name_plural': 'grupos',
                'db_table': 'grupos',
                'ordering': ['nombre'],
            },
        ),
        migrations.CreateModel(
            name='GrupoXUsuario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('es_supervisor', models.BooleanField(default=False)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('grupo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='membresias', to='grupos.grupo')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='membresias_grupo', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'miembro de grupo',
                'db_table': 'grupos_x_usuario',
                'ordering': ['grupo_id', '-es_supervisor', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='grupoxusuario',
            constraint=models.UniqueConstraint(fields=['grupo', 'usuario'], name='uq_grupo_x_usuario'),
        ),
        migrations.AddIndex(
            model_name='grupoxusuario',
            index=models.Index(fields=['grupo', 'es_supervisor'], name='ix_gxu_grupo_supervisor'),
        ),
    ]
