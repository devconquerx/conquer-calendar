from django.db import migrations


PERMISOS_FASE_02 = [
    ('event_types.ver', 'Ver tipos de evento propios'),
    ('event_types.crear', 'Crear tipos de evento'),
    ('event_types.editar', 'Editar tipos de evento'),
    ('event_types.eliminar', 'Eliminar tipos de evento'),
    ('availability.ver', 'Ver disponibilidad propia'),
    ('availability.editar', 'Editar disponibilidad propia'),
]


def forwards(apps, schema_editor):
    Permiso = apps.get_model('permisos', 'Permiso')
    Rol = apps.get_model('permisos', 'Rol')
    PermisoXRol = apps.get_model('permisos', 'PermisoXRol')

    for cn, nm in PERMISOS_FASE_02:
        permiso, _ = Permiso.objects.update_or_create(codename=cn, defaults={'nombre': nm})

    admin_rol = Rol.objects.get(nombre='admin')
    host_rol = Rol.objects.get(nombre='host')

    for cn, _ in PERMISOS_FASE_02:
        permiso = Permiso.objects.get(codename=cn)
        PermisoXRol.objects.get_or_create(rol=admin_rol, permiso=permiso)
        PermisoXRol.objects.get_or_create(rol=host_rol, permiso=permiso)


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('permisos', '0002_seed_permisos_y_roles'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
