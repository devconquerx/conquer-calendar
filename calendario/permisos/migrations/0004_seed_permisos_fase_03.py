from django.db import migrations


PERMISOS_FASE_03 = [
    ('reservas.ver_propias', 'Ver reservas propias'),
    ('reservas.cancelar', 'Cancelar reservas propias'),
]


def forwards(apps, schema_editor):
    Permiso = apps.get_model('permisos', 'Permiso')
    Rol = apps.get_model('permisos', 'Rol')
    PermisoXRol = apps.get_model('permisos', 'PermisoXRol')

    for cn, nm in PERMISOS_FASE_03:
        Permiso.objects.update_or_create(codename=cn, defaults={'nombre': nm})

    admin_rol = Rol.objects.get(nombre='admin')
    host_rol = Rol.objects.get(nombre='host')

    for cn, _ in PERMISOS_FASE_03:
        permiso = Permiso.objects.get(codename=cn)
        PermisoXRol.objects.get_or_create(rol=admin_rol, permiso=permiso)
        PermisoXRol.objects.get_or_create(rol=host_rol, permiso=permiso)


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('permisos', '0003_seed_permisos_fase_02'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
