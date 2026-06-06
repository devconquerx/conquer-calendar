# -*- coding: utf-8 -*-
# Ajusta el contenido de la landing de conquer-blocks/latam para que coincida
# EXACTO con producción (www.conquerblocks.com).
import json

from django.db import migrations

PAYLOAD = "{\"conquer-blocks|latam\": {\"title\": \"La persona promedio que aprendió la profesión que estás a punto de descubrir, consiguió un <strong><em>puesto de trabajo en remoto</em></strong> y con un salario de más de <strong>3000 dólares al mes</strong>\", \"subtitle\": \"Vídeo gratis de 15 minutos\", \"description\": \"... aunque no tengas conocimientos previos de tecnología, ni te consideres una persona técnica\", \"bullets\": [\"<strong>Tu trabajo no te llena,</strong> y quieres un cambio profesional que te permita evolucionar aprendiendo una profesión de futuro.\", \"Los precios de la comida, luz, alquiler, combustible, etc., <strong>no paran de subir</strong>, y necesitas una profesión con mejores salarios.\", \"Descubre una nueva vía para tener más libertad, <strong>tiempo para ti y tu familia.</strong>\"], \"buttonText\": \"Ver vídeo gratis\", \"instructor\": {\"name\": \"Bienvenido Sáez\", \"role\": \"Bienvenido es Director de Educación Tecnológica en Conquer Blocks.\", \"description\": \"Con el método que te presentará en el vídeo gratis, ha ayudado a más de <strong>6.000</strong> personas a aprender una nueva profesión con la que cambiar sus vidas por completo.\", \"imageUrl\": \"https://cdn.prod.website-files.com/63c2c7b1f3d9c51c32335fb0/66506bf3656479db9e7361e9_bienvenido-cuadrado.avif\"}, \"disclaimer\": \"* El curso y la clase son únicamente educativos e informativos. No constituyen asesoramiento financiero ni laboral. Los resultados no están garantizados y pueden variar según cada persona.\"}}"


def forwards(apps, schema_editor):
    FunnelForm = apps.get_model('funnels', 'FunnelForm')
    data = json.loads(PAYLOAD)
    for key, landing in data.items():
        escuela, region = key.split('|')
        for ff in FunnelForm.objects.filter(escuela=escuela, region=region):
            cfg = ff.config or {}
            cfg['landing'] = landing
            ff.config = cfg
            ff.save(update_fields=['config'])


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('funnels', '0002_landing_content'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
