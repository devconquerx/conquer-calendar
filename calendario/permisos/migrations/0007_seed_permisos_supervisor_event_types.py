from django.db import migrations


def forwards(apps, schema_editor):
    Permiso = apps.get_model('permisos', 'Permiso')
    Rol = apps.get_model('permisos', 'Rol')
    PermisoXRol = apps.get_model('permisos', 'PermisoXRol')

    supervisor_rol = Rol.objects.get(nombre='supervisor')

    for codename in ['event_types.ver', 'event_types.editar']:
        permiso = Permiso.objects.get(codename=codename)
        PermisoXRol.objects.get_or_create(rol=supervisor_rol, permiso=permiso)


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('permisos', '0006_seed_permisos_grupos'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
