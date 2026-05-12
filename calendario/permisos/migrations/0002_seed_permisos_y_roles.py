from django.db import migrations


PERMISOS = [
    ('panel.acceder', 'Acceder al panel interno'),
    ('usuarios.ver', 'Ver usuarios'),
    ('usuarios.crear', 'Crear usuarios'),
    ('usuarios.editar', 'Editar usuarios'),
    ('usuarios.cambiar_password', 'Cambiar password de otros usuarios'),
    ('usuarios.activar', 'Activar/desactivar usuarios'),
    ('usuarios.eliminar', 'Eliminar usuarios'),
    ('roles.ver', 'Ver roles'),
    ('roles.crear', 'Crear roles'),
    ('roles.editar', 'Editar roles'),
    ('roles.eliminar', 'Eliminar roles'),
    ('permisos.ver', 'Ver catálogo de permisos'),
]


def forwards(apps, schema_editor):
    Permiso = apps.get_model('permisos', 'Permiso')
    Rol = apps.get_model('permisos', 'Rol')
    PermisoXRol = apps.get_model('permisos', 'PermisoXRol')
    RolXUsuario = apps.get_model('permisos', 'RolXUsuario')
    User = apps.get_model('users', 'User')

    for codename, nombre in PERMISOS:
        Permiso.objects.update_or_create(codename=codename, defaults={'nombre': nombre})

    admin_rol, _ = Rol.objects.update_or_create(
        nombre='admin',
        defaults={'descripcion': 'Administrador del calendario'},
    )
    host_rol, _ = Rol.objects.update_or_create(
        nombre='host',
        defaults={'descripcion': 'Trabajador / receptor de reservas'},
    )

    for codename, _ in PERMISOS:
        p = Permiso.objects.get(codename=codename)
        PermisoXRol.objects.get_or_create(rol=admin_rol, permiso=p)

    panel_permiso = Permiso.objects.get(codename='panel.acceder')
    PermisoXRol.objects.get_or_create(rol=host_rol, permiso=panel_permiso)

    for u in User.objects.filter(is_superuser=True):
        RolXUsuario.objects.get_or_create(usuario=u, rol=admin_rol)


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('permisos', '0001_initial'),
        ('users', '0002_alter_user_options_remove_user_full_name_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
