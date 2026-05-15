from django.db import migrations


def forwards(apps, schema_editor):
    Permiso = apps.get_model('permisos', 'Permiso')
    Rol = apps.get_model('permisos', 'Rol')
    PermisoXRol = apps.get_model('permisos', 'PermisoXRol')

    permiso, _ = Permiso.objects.update_or_create(
        codename='reservas.ver_todas',
        defaults={'nombre': 'Ver todas las reservas'},
    )
    admin_rol = Rol.objects.get(nombre='admin')
    PermisoXRol.objects.get_or_create(rol=admin_rol, permiso=permiso)


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('permisos', '0004_seed_permisos_fase_03'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
