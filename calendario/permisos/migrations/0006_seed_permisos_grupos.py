from django.db import migrations


PERMISOS_NUEVOS = {
    'grupos.ver': 'Ver grupos',
    'grupos.crear': 'Crear grupos',
    'grupos.editar': 'Editar grupos',
    'grupos.eliminar': 'Eliminar grupos',
    'grupos.editar_propio': 'Editar permisos del propio grupo',
    'usuarios.editar_grupo': 'Editar usuarios del grupo supervisado',
}

PERMISOS_ADMIN = ['grupos.ver', 'grupos.crear', 'grupos.editar', 'grupos.eliminar']

PERMISOS_SUPERVISOR = ['grupos.ver', 'grupos.editar_propio', 'usuarios.editar_grupo']

PERMISOS_SUPERVISOR_EXTRA = ['panel.acceder', 'reservas.ver_propias']


def forwards(apps, schema_editor):
    Permiso = apps.get_model('permisos', 'Permiso')
    Rol = apps.get_model('permisos', 'Rol')
    PermisoXRol = apps.get_model('permisos', 'PermisoXRol')

    for codename, nombre in PERMISOS_NUEVOS.items():
        Permiso.objects.update_or_create(codename=codename, defaults={'nombre': nombre})

    admin_rol = Rol.objects.get(nombre='admin')
    for codename in PERMISOS_ADMIN:
        permiso = Permiso.objects.get(codename=codename)
        PermisoXRol.objects.get_or_create(rol=admin_rol, permiso=permiso)

    supervisor_rol, _ = Rol.objects.update_or_create(
        nombre='supervisor',
        defaults={'descripcion': 'Supervisor de grupo'},
    )

    for codename in PERMISOS_SUPERVISOR_EXTRA + PERMISOS_SUPERVISOR:
        permiso = Permiso.objects.get(codename=codename)
        PermisoXRol.objects.get_or_create(rol=supervisor_rol, permiso=permiso)


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('permisos', '0005_seed_reservas_ver_todas'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
