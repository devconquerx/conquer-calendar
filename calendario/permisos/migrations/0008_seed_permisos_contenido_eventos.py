# -*- coding: utf-8 -*-
"""Permisos de la pantalla de textos de las páginas de evento.

Van aparte de los del admin de Django a propósito: la idea es poder dar de alta
a quien escribe la copia sin darle el admin entero.
"""
from django.db import migrations


PERMISOS = {
    'contenido_eventos.ver': 'Ver los textos de las páginas de evento',
    'contenido_eventos.editar': 'Editar y publicar los textos de las páginas de evento',
}


def forwards(apps, schema_editor):
    Permiso = apps.get_model('permisos', 'Permiso')
    Rol = apps.get_model('permisos', 'Rol')
    PermisoXRol = apps.get_model('permisos', 'PermisoXRol')

    for codename, nombre in PERMISOS.items():
        Permiso.objects.update_or_create(codename=codename, defaults={'nombre': nombre})

    rol_admin = Rol.objects.filter(nombre='admin').first()
    if not rol_admin:
        return
    for codename in PERMISOS:
        PermisoXRol.objects.get_or_create(
            rol=rol_admin, permiso=Permiso.objects.get(codename=codename))


def reverse(apps, schema_editor):
    Permiso = apps.get_model('permisos', 'Permiso')
    Permiso.objects.filter(codename__in=PERMISOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('permisos', '0007_seed_permisos_supervisor_event_types'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
